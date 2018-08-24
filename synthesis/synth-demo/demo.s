	.file	"demo.c"
	.section	.rodata
.LC0:
	.string	"I'm %d; how many? %n\n"
	.text
	.globl	bar
	.type	bar, @function
bar:
.LFB0:
	.cfi_startproc
	subq	$24, %rsp
	.cfi_def_cfa_offset 32
	movl	%edi, 12(%rsp)
	movl	12(%rsp), %eax
	leaq	12(%rsp), %rdx
	movl	%eax, %esi
	movl	$.LC0, %edi
	movl	$0, %eax
	call	printf
	movl	12(%rsp), %eax
	addq	$24, %rsp
	.cfi_def_cfa_offset 8
	ret
	.cfi_endproc
.LFE0:
	.size	bar, .-bar
	.globl	foo
	.type	foo, @function
foo:
.LFB1:
	.cfi_startproc
	subq	$8, %rsp
	.cfi_def_cfa_offset 16
	movl	$3, %edi
	call	bar
	addq	$8, %rsp
	.cfi_def_cfa_offset 8
	ret
	.cfi_endproc
.LFE1:
	.size	foo, .-foo
	.globl	main
	.type	main, @function
main:
.LFB2:
	.cfi_startproc
	subq	$8, %rsp
	.cfi_def_cfa_offset 16
	movl	$0, %eax
	call	foo
	addq	$8, %rsp
	.cfi_def_cfa_offset 8
	ret
	.cfi_endproc
.LFE2:
	.size	main, .-main
	.ident	"GCC: (GNU) 6.4.0"
	.section	.note.GNU-stack,"",@progbits
