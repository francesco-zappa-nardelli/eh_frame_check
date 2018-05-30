### TO PASS MORE ARGUMENTS TO `./run_test.py`, please set the environment
### variable `TEST_ARGS` to whatever you want, eg.
###     TEST_ARGS=--keep-on-timeout make

## PARAMETERS #################################################################
# Override this variable with environment to run only a subdirectory
TESTS_DIR ?= glibc/build

OUTPUT_DIR ?= $(DEFAULT_OUTPUT_DIR)

TEST_ARGS ?=
## END PARAMETERS #############################################################

TESTS := $(shell find "$(TESTS_DIR)" -executable -name 'test-*' \
	-or -executable -name 'tst-*')
TESTS_SUFFIX := $(TESTS:=.test)
DEFAULT_OUTPUT_DIR := outputs/$(shell date +%F_%H-%M-%S)

all: $(TESTS_SUFFIX)

.PHONY: %.test %.test.stdout
%.test: %
	@echo "$<…"
	@bash -c 'python3 ./run_test.py $(TEST_ARGS) \
		"$<" --output "$(OUTPUT_DIR)" || true'


%.test.stdout: %
	@echo "$<…"
	@bash -c 'python3 ./run_test.py $(TEST_ARGS) "$<" || true'
