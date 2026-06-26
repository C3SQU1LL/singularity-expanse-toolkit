# The Singularity Expanse Toolkit - GitHub Pages Edition

This version needs no Python or app installation on your laptop.

## What it does in the browser
- Opens `.solar`, `.json`, or `.txt` generator files
- Previews star, planet, and moon records
- Exports CSV files for Notion import

## Important
A pure GitHub Pages website cannot safely perform direct Notion API imports. For automatic Notion import without installing anything, use the included GitHub Actions workflow. GitHub runs the Python importer online.

## Setup summary
1. Upload all files in this folder to your GitHub repository.
2. Enable GitHub Pages for `main` / root.
3. Add your Notion token as a GitHub secret named `NOTION_TOKEN`.
4. Upload `.solar` files into the `imports` folder.
5. Run the `Import .solar to Notion` workflow from the Actions tab.
