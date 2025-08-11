import requests
import sys
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class AppIconFinder:
    """
    A class for finding application icons from either the dashboard-icons repository
    or by extracting favicons from an application's homepage.
    """

    def __init__(self):
        """
        Initialize the AppIconFinder with default headers for HTTP requests.
        """
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_app_icon(self, app_name, homepage_url):
        """
        Main function to get an application icon.

        Args:
            app_name (str): The name of the application.
            homepage_url (str): The URL of the application's homepage.

        Returns:
            str: Either the normalized app_name (if found in dashboard-icons),
                 a favicon URL, or "default" if no icon is found.
        """
        # First check if the icon exists in dashboard-icons
        dashboard_icon = self._find_dashboard_icon(app_name)
        if dashboard_icon:
            return dashboard_icon

        # If not, try to find the favicon
        favicon_url = self._find_favicon_url(homepage_url)
        if favicon_url:
            return favicon_url

        # Return default if no favicon found
        return "default"

    def _find_dashboard_icon(self, app_name):
        normalized_name = app_name.lower().replace(" ", "-")
        url = f"https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/{normalized_name}.png"
        try:
            response = requests.head(
                url,
                headers=self.headers,
                timeout=10,
                allow_redirects=True
            )
            if response.status_code == 200:
                return normalized_name
            return None
        except requests.RequestException:
            return None

    def _find_favicon_url(self, homepage_url):
        try:
            if not homepage_url:
                return None

            # Make sure URL has a scheme
            homepage_url = homepage_url.strip()
            if not homepage_url.startswith(('http://', 'https://')):
                homepage_url = 'https://' + homepage_url

            # Fetch the homepage
            response = requests.get(homepage_url, headers=self.headers, timeout=10)
            response.raise_for_status()

            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for favicon in different ways
            # 1. Check for link tags with rel="icon" or rel="shortcut icon"
            icon_links = soup.find_all('link', rel=re.compile(r'(shortcut icon|icon|apple-touch-icon)', re.I))
            if icon_links:
                # Sort by preference: apple-touch-icon > icon > shortcut icon
                def get_priority(link):
                    rel_attr = link.get('rel', [])
                    if isinstance(rel_attr, str):
                        rel_attr = [rel_attr]
                    rel_lower = ' '.join(rel_attr).lower()
                    if 'apple-touch-icon' in rel_lower:
                        return 3
                    elif 'icon' in rel_lower and 'shortcut' not in rel_lower:
                        return 2
                    else:
                        return 1

                icon_links = sorted(icon_links, key=get_priority, reverse=True)
                for link in icon_links:
                    if 'href' in link.attrs:
                        # Make relative URLs absolute
                        favicon_url = urljoin(homepage_url, link['href'])
                        return favicon_url

            # 2. Check for the default location
            default_favicon = urljoin(homepage_url, '/favicon.ico')
            favicon_response = requests.head(default_favicon, headers=self.headers, timeout=5)
            if favicon_response.status_code == 200:
                return default_favicon
            return None
        except Exception as e:
            print(f"Error finding favicon: {e}", file=sys.stderr)
            return None


def main():
    """
    Test the AppIconFinder with some popular applications.
    """
    # Create an instance of AppIconFinder
    icon_finder = AppIconFinder()

    # Test cases - popular applications and their homepages
    test_cases = [
        ("GitHub", "github.com"),
        ("Gitea", "about.gitea.com"),
        ("Plex", "plex.tv"),
        ("Sonarr", "sonarr.tv"),
        ("Radarr", "radarr.video"),
        ("Grafana", "grafana.com"),
        ("Jellyfin", "jellyfin.org"),
        ("HUP", "hup.hu")
    ]

    # Test each application
    for app_name, homepage in test_cases:
        icon_result = icon_finder.get_app_icon(app_name, homepage)
        print(f"App: {app_name}, Homepage: {homepage}, Icon: {icon_result}")


if __name__ == "__main__":
    main()
