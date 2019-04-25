#################################################################################
# GLOBALS                                                                       #
#################################################################################

# Change these!
PROJECT_NAME = lead_lag_pilot
PROJECT_PYTHON_VERSION = 0.1.0

# No changes needed!.. Unless you know what you are doing.
PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

#################################################################################
# COMMANDS                                                                      #
#################################################################################

## Freeze Python Dependencies
freze_requirements:
	pip freeze -q -r requirements.txt | grep -B100 "pip freeze" | grep -v "pip freeze" > requirements-tmp.txt
	mv requirements-tmp.txt requirements.txt

## Install Python Dependencies
requirements:
	pip install -r requirements.txt
	pip install -e .
	@echo "Remmember to install amplify trader and amplify charts"

## Delete all compiled Python files
clean:
	find . -name "*.pyc" -exec rm {} \;

## Adds environment variables to .envrc
add_env_vars:
	make check_make_file
	touch .envrc
	@echo "export PROJECT_DIR='"$(shell pwd)"'" >> .envrc
	@echo "DATABASE='postgresql://trader:<password>@data.arcane.no/trader'" >> .envrc

# Compile the docs.
doc:
	cd docs && $(MAKE) html

# Opens the documentation. (not tested on mac/windows.)
open_doc:
	google-chrome $(PROJECT_DIR)/docs/build/html/index.html

# Deletes docs/_build directory
clean_doc:
	rm -rf docs/build/

## Build the cython code
cython:
	python setup.py build_ext --inplace

#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := show-help

# Inspired by <http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html>
# sed script explained:
# /^##/:
# 	* save line in hold space
# 	* purge line
# 	* Loop:
# 		* append newline + line to hold space
# 		* go to next line
# 		* if line starts with doc comment, strip comment character off and loop
# 	* remove target prerequisites
# 	* append hold space (+ newline) to line
# 	* replace newline plus comments by `---`
# 	* print line
# Separate expressions are necessary because labels cannot be delimited by
# semicolon; see <http://stackoverflow.com/a/11799865/1968>
.PHONY: show-help
show-help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=19 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')
