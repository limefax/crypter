BLUE = '\033[94m'
CYAN = '\033[96m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'



def info(msg):
    output = f'{CYAN}[+] {ENDC}{msg}'
    print(output)


def warn(msg):
    output = f'{WARNING}[!] {ENDC}{msg}'
    print(output)


def error(msg):
    output = f'{FAIL}[X] {ENDC}{msg}'
    print(output)


def debug(msg):
    output = f'{BLUE}[?] {ENDC}{msg}'
    print(output)


if __name__ == '__main__':
    info('info')
    warn('warn')
    error('error')
    debug('debug')
