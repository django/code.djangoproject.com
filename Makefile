CSS = trac-env/htdocs/css
SCSS = scss

compile-scss:
	sassc $(SCSS)/trachacks.scss $(CSS)/trachacks.css -s compressed

compile-scss-debug:
	sassc $(SCSS)/trachacks.scss $(CSS)/trachacks.css --sourcemap
