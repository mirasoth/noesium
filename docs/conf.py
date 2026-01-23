# Configuration file for the Sphinx documentation builder.

project = 'your-project-name'
copyright = '2025-2026, Mirasoth Inc.'
author = 'Mirasoth Team'
release = '0.1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme' 