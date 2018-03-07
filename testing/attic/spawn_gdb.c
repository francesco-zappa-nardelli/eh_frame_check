#include <unistd.h>
#include <sys/types.h>
#include <errno.h>
#include <stdio.h>
#include <sys/wait.h>
#include <stdlib.h>


int main(void) {
  pid_t childPID;
  int status;

    
  childPID = fork();

  if(childPID >= 0) { // fork was successful
    if(childPID == 0) { // child process
      printf("\n Child Process \n ");
      static char *argv[]={"bash", "-x", "nhat2.sh", NULL};
      setpgrp();
      printf("\n AFTER SETPGRP \n ");
      execv("/bin/bash",argv);
      printf("\n Child Process end \n ");

    }
    else //Parent process
      {
        printf("\n Parent start \n");
        wait(&status);
        printf("\n Parent end \n");
      }
  }
  else { // fork failed
    printf("\n Fork failed, quitting!!!!!!\n");
    return 1;
  }

  return 0;
}


/* int main(void) { */
/*   pid_t childPID; */
/*   int status; */

    
/*   childPID = fork(); */

/*   if(childPID >= 0) { // fork was successful */
/*     if(childPID == 0) { // child process */
/*       printf("\n Child Process \n "); */
/*       static char *argv[]={"gdb", "-x", "/home/zappa/repos/zappa/dwarf/src-fzn/eh_frame_check.py", "input" ,NULL}; */
/*       setpgrp(); */
/*       printf("\n AFTER SETPGRP \n "); */
/*       execv("/home/zappa/source/gdb-py27/bin/gdb",argv); */
/*       printf("\n Child Process end \n "); */

/*     } */
/*     else //Parent process */
/*       { */
/*         printf("\n Parent start \n"); */
/*         wait(&status); */
/*         printf("\n Parent end \n"); */
/*       } */
/*   } */
/*   else { // fork failed */
/*     printf("\n Fork failed, quitting!!!!!!\n"); */
/*     return 1; */
/*   } */

/*   return 0; */
/* } */


