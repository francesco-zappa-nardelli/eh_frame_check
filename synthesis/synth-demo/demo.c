#include <stdio.h>

int bar(int x) {
  printf("I'm %d; how many? %n\n", x, &x);
  return x;
}

int foo() {
  return bar(3);
}

int main() {
  return foo();
}
  
