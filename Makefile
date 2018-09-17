CSS = trac-env/htdocs/css
SCSS = scss

compile-scss:
	pysassc $(SCSS)/trachacks.scss $(CSS)/trachacks.css -s compressed

compile-scss-debug:
	pysassc $(SCSS)/trachacks.scss $(CSS)/trachacks.css --sourcemap
