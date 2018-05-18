## PARAMETERS #################################################################
# Override this variable with environment to run only a subdirectory
TESTS_DIR ?= glibc/build

OUTPUT_DIR ?= $(DEFAULT_OUTPUT_DIR)
## END PARAMETERS #############################################################

TESTS := $(shell find "$(TESTS_DIR)" -executable -name 'test-*' \
	-or -executable -name 'tst-*')
TESTS_SUFFIX := $(TESTS:=.test)
DEFAULT_OUTPUT_DIR := outputs/$(shell date +%F_%H-%M-%S)

all: $(TESTS_SUFFIX)

.PHONY: %.test %.test.stdout
%.test: %
	@echo "$<…"
	@bash -c 'python3 ./run_test.py "$<" "$(OUTPUT_DIR)" || true'


%.test.stdout: %
	@echo "$<…"
	@bash -c 'python3 ./run_test.py "$<" || true'
