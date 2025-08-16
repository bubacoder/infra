#!/usr/bin/env python3

import argparse
import sys
import requests
from datetime import datetime


def get_docker_hub_tags(image_name, limit=10, architecture="linux/amd64"):
    """Query Docker Hub for image tags with timestamp information."""
    # Parse repository name
    if '/' in image_name:
        namespace, repo = image_name.split('/', 1)
    else:
        namespace = 'library'  # Official images are in the 'library' namespace
        repo = image_name

    url = f"https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags?page_size=100"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        tag_data = []

        for tag in data.get('results', []):
            # Find the image info for the requested architecture
            arch_digest = None
            arch_os, arch_variant = architecture.split('/')
            for image in tag.get('images', []):
                if image.get('architecture') == arch_variant and image.get('os') == arch_os:
                    arch_digest = image.get('digest')
                    break

            tag_data.append({
                'name': tag['name'],
                'last_updated': tag.get('last_updated'),
                'size': tag.get('full_size', 0),
                'digest': arch_digest
            })

        # Handle pagination if there are more tags
        while 'next' in data and data['next'] and len(tag_data) < 1000:  # Limit to avoid too many requests
            response = requests.get(data['next'])
            response.raise_for_status()
            data = response.json()

            for tag in data.get('results', []):
                # Find the image info for the requested architecture
                arch_digest = None
                arch_os, arch_variant = architecture.split('/')
                for image in tag.get('images', []):
                    if image.get('architecture') == arch_variant and image.get('os') == arch_os:
                        arch_digest = image.get('digest')
                        break

                tag_data.append({
                    'name': tag['name'],
                    'last_updated': tag.get('last_updated'),
                    'size': tag.get('full_size', 0),
                    'digest': arch_digest
                })

        # Sort by last_updated in descending order (newest first)
        tag_data.sort(key=lambda x: x['last_updated'] if x['last_updated'] else '', reverse=True)
        return tag_data
    except requests.exceptions.RequestException as e:
        print(f"Error querying Docker Hub: {e}", file=sys.stderr)
        return []


def get_registry_tags(registry_url, image_name, limit=10, architecture="linux/amd64"):
    """Query a registry API v2 for image tags and attempt to get creation time."""
    url = f"{registry_url}/v2/{image_name}/tags/list"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        tags = data.get('tags', [])

        # For Docker Registry API v2, we need to make additional requests to get manifest and timestamps
        tag_data = []
        for tag in tags[:100]:  # Limit the number of additional requests
            manifest_url = f"{registry_url}/v2/{image_name}/manifests/{tag}"
            try:
                # Try to get the manifest to extract creation time
                headers = {'Accept': 'application/vnd.docker.distribution.manifest.v2+json'}
                manifest_response = requests.get(manifest_url, headers=headers)
                manifest_response.raise_for_status()

                # Get digest from the manifest
                manifest = manifest_response.json()

                # For multi-arch images, we need to find the digest for the specific architecture
                digest = None
                # Try to parse the architecture from the manifest if it's a multi-arch image
                if 'manifests' in manifest:
                    for m in manifest.get('manifests', []):
                        if m.get('platform', {}).get('architecture') == architecture.split('/')[1] and \
                           m.get('platform', {}).get('os') == architecture.split('/')[0]:
                            digest = m.get('digest')
                            break
                else:
                    # If it's not a multi-arch manifest, just use the digest directly
                    digest = manifest_response.headers.get('Docker-Content-Digest')

                # Most registry implementations don't expose creation time directly in the API
                # We'll use the response headers as a rough proxy for recency
                last_modified = manifest_response.headers.get('Last-Modified')
                tag_data.append({
                    'name': tag,
                    'last_updated': last_modified,
                    'digest': digest
                })
            except requests.exceptions.RequestException:
                # If we can't get detailed info, just use the tag name
                tag_data.append({
                    'name': tag,
                    'last_updated': None,
                    'digest': None
                })

        # Sort by last_updated in descending order if available
        tag_data.sort(key=lambda x: x['last_updated'] if x['last_updated'] else '', reverse=True)
        return tag_data
    except requests.exceptions.RequestException as e:
        print(f"Error querying registry: {e}", file=sys.stderr)
        return []


def format_datetime(datetime_str):
    """Format datetime string to a more readable format."""
    if not datetime_str:
        return "Unknown"
    try:
        # Parse ISO format
        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except ValueError:
        # Try to parse HTTP date format
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(datetime_str)
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except Exception:
            return datetime_str


def format_size(size_bytes):
    """Format size in bytes to human-readable format."""
    if not size_bytes:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def format_digest(digest):
    """Format the digest to a shorter representation if present."""
    if not digest:
        return "N/A"
    # If the digest is in the form "sha256:abcdef123456...", just show the first 12 chars of the hash
    if ":" in digest:
        algo, hash_value = digest.split(":", 1)
        return f"{algo}:{hash_value[:12]}..."
    return digest


def get_tags_by_digest(tags, target_digest):
    """Filter tags that have the same digest."""
    if not target_digest:
        return []

    return [tag for tag in tags if tag.get('digest') == target_digest]


def determine_tag_specificity(tag):
    """Determine how specific a version tag is, higher is more specific.

    Examples:
    - '1' -> low specificity
    - '1.29' -> medium specificity
    - '1.29.1-bookworm' -> high specificity

    This function attempts to handle semantic versioning as well as various edge cases.
    """
    # Skip non-version tags (no digits)
    if not any(c.isdigit() for c in tag):
        return -1

    # Skip tags that start with non-digits and aren't version tags
    if not tag[0].isdigit() and '-' not in tag:
        return -1

    # Base score starts at 0
    score = 0

    # Split by common separators
    parts = tag.replace('-', '.').replace('_', '.').split('.')

    # Count numeric segments (major.minor.patch get higher scores)
    numeric_parts = []
    for p in parts:
        if p.isdigit():
            numeric_parts.append(p)
        else:
            break  # Stop at the first non-digit part
    score += len(numeric_parts) * 100  # Higher weight for more version segments

    # Add points for parts containing letters but no numbers, or both letters and numbers
    for part in parts:
        has_alpha = any(c.isalpha() for c in part)
        has_digit = any(c.isdigit() for c in part)
        if has_alpha and not has_digit:
            score += 10
        elif has_alpha and has_digit:
            score += 15

    # Count total segments (more specific tags have more segments)
    score += len(parts) * 5

    # Penalize 'latest' and 'stable' tags
    if tag.lower() in ['latest', 'stable']:
        score = -100

    return score


def list_recent_tags(args):
    """List recent tags for an image."""
    # Store quiet flag to local variable for easier access
    quiet = args.quiet if hasattr(args, 'quiet') else False

    # Determine if we should print any output
    should_output = not quiet

    # Parse the image name to determine if it includes a registry
    if '/' in args.image and ('.' in args.image.split('/')[0] or ':' in args.image.split('/')[0]):
        # This looks like a hostname with a port or domain name
        parts = args.image.split('/')
        registry_host = parts[0]
        image_name = '/'.join(parts[1:])

        if args.registry:
            registry_url = args.registry
        else:
            # Assume HTTPS
            registry_url = f"https://{registry_host}"

        if should_output:
            print(f"Querying registry {registry_url} for {image_name} (architecture: {args.architecture})...")
        tags = get_registry_tags(registry_url, image_name, args.limit, args.architecture)
    else:
        # Use Docker Hub
        if should_output:
            print(f"Querying Docker Hub for {args.image} (architecture: {args.architecture})...")
        tags = get_docker_hub_tags(args.image, args.limit, args.architecture)

    if tags:
        # Only take up to limit
        tags = tags[:args.limit]

        if quiet:
            # In quiet mode, just output the tag names, one per line
            for tag in tags:
                print(tag['name'])
        else:
            # Detailed output
            print(f"\nMost recent {len(tags)} tags for {args.image} ({args.architecture}):")
            print(f"{'TAG':<30} {'LAST UPDATED':<30} {'SIZE':<15} {'DIGEST':<20}")
            print("-" * 95)

            for tag in tags:
                updated = format_datetime(tag.get('last_updated'))
                size = format_size(tag.get('size')) if 'size' in tag else 'N/A'
                digest = format_digest(tag.get('digest'))
                print(f"{tag['name']:<30} {updated:<30} {size:<15} {digest:<20}")
    elif not quiet:
        print(f"No tags found for {args.image}")


def list_same_hash_tags(args, suppress_output=False):
    """List tags that have the same hash as the specified tag.

    Args:
        args: Command line arguments
        suppress_output: If True, suppress all output regardless of quiet flag
    """
    # Store quiet flag to local variable for easier access
    quiet = args.quiet if hasattr(args, 'quiet') else False

    # Determine if we should print any output
    should_output = not suppress_output and not quiet

    # Parse the image name to determine if it includes a registry
    if '/' in args.image and ('.' in args.image.split('/')[0] or ':' in args.image.split('/')[0]):
        # This looks like a hostname with a port or domain name
        parts = args.image.split('/')
        registry_host = parts[0]
        image_name = '/'.join(parts[1:])

        if args.registry:
            registry_url = args.registry
        else:
            # Assume HTTPS
            registry_url = f"https://{registry_host}"

        if should_output:
            print(f"Querying registry {registry_url} for {image_name} (architecture: {args.architecture})...")
        all_tags = get_registry_tags(registry_url, image_name, 1000, args.architecture)  # Get many tags to search through
    else:
        # Use Docker Hub
        if should_output:
            print(f"Querying Docker Hub for {args.image} (architecture: {args.architecture})...")
        all_tags = get_docker_hub_tags(args.image, 1000, args.architecture)  # Get many tags to search through

    if not all_tags:
        if should_output:
            print(f"No tags found for {args.image}")
        return

    # Find the target tag to get its digest
    tag_name = args.tag if args.tag else all_tags[0]['name']  # Use first tag if none specified
    target_tag = next((t for t in all_tags if t['name'] == tag_name), None)

    if not target_tag:
        if should_output:
            print(f"Tag '{tag_name}' not found for {args.image}")
        return

    target_digest = target_tag.get('digest')
    if not target_digest:
        if should_output:
            print(f"No digest found for tag '{tag_name}'")
        return

    # Find all tags with the same digest
    same_hash_tags = get_tags_by_digest(all_tags, target_digest)

    if same_hash_tags:
        if not suppress_output and quiet:
            # In quiet mode (but not suppressed), output the tag names, one per line
            for tag in same_hash_tags:
                print(tag['name'])
        elif should_output:
            # Detailed output
            print(f"\nTags with the same digest as '{tag_name}' ({format_digest(target_digest)}) for {args.image}:")
            print(f"{'TAG':<30} {'LAST UPDATED':<30} {'SIZE':<15}")
            print("-" * 75)

            for tag in same_hash_tags:
                updated = format_datetime(tag.get('last_updated'))
                size = format_size(tag.get('size')) if 'size' in tag else 'N/A'
                print(f"{tag['name']:<30} {updated:<30} {size:<15}")
    elif should_output:
        print(f"No tags found with the same digest as '{tag_name}'")

    return same_hash_tags


def get_most_specific_tag(args):
    """Find the most specific version tag from a set of tags with the same hash."""
    # Store quiet flag to local variable for easier access
    quiet = args.quiet if hasattr(args, 'quiet') else False

    # First, get all tags with the same hash
    # When in quiet mode, suppress output from list_same_hash_tags
    same_hash_tags = list_same_hash_tags(args, suppress_output=quiet)

    if not same_hash_tags or len(same_hash_tags) < 2:
        # No need to find most specific if there's only one tag
        return

    # Calculate the specificity score for each tag
    tag_scores = []
    for tag in same_hash_tags:
        score = determine_tag_specificity(tag['name'])
        tag_scores.append((tag, score))

    # Sort by specificity score (highest first)
    tag_scores.sort(key=lambda x: x[1], reverse=True)

    # Get the most specific tag
    most_specific = tag_scores[0][0]

    if quiet:
        # Only output the final recommended tag
        print(most_specific['name'])
    else:
        # Detailed output
        print("\nMost specific tag:")
        print(f"{'TAG':<30} {'SPECIFICITY SCORE':<20} {'LAST UPDATED':<30}")
        print("-" * 80)

        updated = format_datetime(most_specific.get('last_updated'))
        print(f"{most_specific['name']:<30} {tag_scores[0][1]:<20} {updated:<30}")

        # Show honorable mentions (other high scoring tags)
        if len(tag_scores) > 1:
            print("\nOther version tags (sorted by specificity):")
            for tag, score in tag_scores[1:6]:  # Show at most 5 other tags
                if score > 0:  # Only show actual version tags
                    updated = format_datetime(tag.get('last_updated'))
                    print(f"{tag['name']:<30} {score:<20} {updated:<30}")

        print(f"\nRecommended tag to use: {most_specific['name']}")

    return most_specific


def main():
    parser = argparse.ArgumentParser(description='Operations on container image tags')
    parser.add_argument('--registry', help='Registry URL (defaults to Docker Hub if not specified)')
    parser.add_argument('--architecture', default='linux/amd64',
                        help='Architecture to query for (default: linux/amd64)')
    parser.add_argument('--quiet', action='store_true', help='Only output final results, no status or progress messages')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create the parser for the "list-recent" command
    recent_parser = subparsers.add_parser('list-recent', help='List recent tags for an image')
    recent_parser.add_argument('image', help='Image name (e.g., nginx or registry.example.com/nginx)')
    recent_parser.add_argument('--limit', type=int, default=10, help='Maximum number of tags to display (default: 10)')
    recent_parser.set_defaults(func=list_recent_tags)

    # Create the parser for the "list-same-hash" command
    hash_parser = subparsers.add_parser('list-same-hash', help='List tags with the same hash')
    hash_parser.add_argument('image', help='Image name (e.g., nginx or registry.example.com/nginx)')
    hash_parser.add_argument('--tag', help='Tag to use as reference (default: latest or first tag found)')
    hash_parser.add_argument('--limit', type=int, default=100, help='Maximum number of tags to search through (default: 100)')
    hash_parser.set_defaults(func=list_same_hash_tags)

    # Create the parser for the "get-most-specific-tag" command
    specific_parser = subparsers.add_parser('get-most-specific-tag', help='Find the most specific version tag from tags with the same hash')
    specific_parser.add_argument('image', help='Image name (e.g., nginx or registry.example.com/nginx)')
    specific_parser.add_argument('--tag', help='Tag to use as reference (default: latest or first tag found)')
    specific_parser.add_argument('--limit', type=int, default=100, help='Maximum number of tags to search through (default: 100)')
    specific_parser.set_defaults(func=get_most_specific_tag)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
