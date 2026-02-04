"""
Shared rich markup color tokens for CLI output.
"""

#============================================
class Colors:
	RED = "[#e60000]"
	DARK_ORANGE = "[#e65400]"
	LIGHT_ORANGE = "[#e69100]"
	DARK_YELLOW = "[#b3b300]"
	LIME_GREEN = "[#59b300]"
	GREEN = "[#009900]"
	TEAL = "[#00b38f]"
	CYAN = "[#00b3b3]"
	SKY_BLUE = "[#0a9bf5]"
	BLUE = "[#0039e6]"
	NAVY = "[#004d99]"
	PURPLE = "[#7b12a1]"
	MAGENTA = "[#b30077]"
	PINK = "[#cc0066]"
	WHITE = "[#ffffff]"

	HEADER = BLUE
	OKBLUE = BLUE
	OKCYAN = CYAN
	OKGREEN = GREEN
	OKMAGENTA = MAGENTA
	WARNING = LIGHT_ORANGE
	FAIL = RED
	ENDC = "[/]"
	BOLD = "[bold]"
	UNDERLINE = "[underline]"
