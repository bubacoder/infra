# Documentation Site

The documentation is written in [Markdown format](https://www.markdownguide.org/) to keep it portable.
A website is built with the [Hugo](https://gohugo.io/) static site generator, using the [Relearn](https://mcshelby.github.io/hugo-theme-relearn/) theme.

## Development

**Build process:** The Markdown and Docker Compose files are collected and converted by `update-docs.py`, then `hugo` build is executed in a Docker container, producing a container image with `nginx` serving the static website.

Run `task docs-deploy` to build and locally deploy (using `docker/stacks/tools/homelab-docs.yaml`) the site.

## Hugo

> [Hugo](https://gohugo.io/) is one of the most popular open-source static site generators. With its amazing speed and flexibility, Hugo makes building websites fun again.

▶️ [Getting Started With Hugo](https://www.youtube.com/watch?v=hjD9jTi_DQ4)

Note - Alternatives to Hugo:
- [Jekyll](https://jekyllrb.com/)
- [Astro](https://astro.build/)

### Installation

Install with APT (older Hugo version):
```sh
sudo apt install hugo
```

...or install a specific [release](https://github.com/gohugoio/hugo/releases) from Github:
```sh
$ wget https://github.com/gohugoio/hugo/releases/download/v0.121.1/hugo_0.121.1_linux-amd64.tar.gz

$ ./hugo version
hugo v0.121.1-00b46fed8e47f7bb0a85d7cfc2d9f1356379b740 linux/amd64 BuildDate=2023-12-08T08:47:45Z VendorInfo=gohugoio
```

...or use Docker:
[Hugo Docker Images](https://hugomods.com/docs/docker/)  
Use `docker pull hugomods/hugo:exts` to update Hugo.

### Theme

- https://mcshelby.github.io/hugo-theme-relearn/
- https://mcshelby.github.io/hugo-theme-relearn/basics/installation/index.html
- https://github.com/McShelby/hugo-theme-relearn/blob/main/exampleSite/

Clone repo:
`git clone https://github.com/McShelby/hugo-theme-relearn.git --depth 1`

### Create and serve a new website

Initialize the new site:
```sh
hugo new site <site_name> -f yaml
```

Output:
```
Congratulations! Your new Hugo site is created in <.../site_name>.

Just a few more steps and you're ready to go:

1. Download a theme into the same-named folder.
   Choose a theme from https://themes.gohugo.io/ or
   create your own with the "hugo new theme <THEMENAME>" command.
2. Perhaps you want to add some content. You can add single files
   with "hugo new <SECTIONNAME>/<FILENAME>.<FORMAT>".
3. Start the built-in live server via "hugo server".

Visit https://gohugo.io/ for quickstart guide and full documentation.
```

Install the theme:
```sh
cd <site_name>
hugo mod get -u https://github.com/McShelby/hugo-theme-relearn.git
```

Run the webserver, allowing remote HTTP access:
```
hugo serve --bind=0.0.0.0 --baseURL=http://0.0.0.0:1313
```
