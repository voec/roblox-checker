import requests, random, string, time, logging, argparse, sys
from itertools import product
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_NAMES = 10
DEFAULT_LENGTH = 4
DEFAULT_BIRTHDAY = '1999-04-20'
DEFAULT_OUTPUT_FILE = 'valid.txt'
DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_FACTOR = 1.5
DEFAULT_TIMEOUT = 10
DEFAULT_DELAY = 0.1
DEFAULT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
]

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    GRAY = '\033[90m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def create_session(retries=DEFAULT_MAX_RETRIES, backoff_factor=DEFAULT_BACKOFF_FACTOR,
                   status_forcelist=(429, 500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(['GET'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

class UserAgentRotator:
    def __init__(self, user_agents=DEFAULT_USER_AGENTS):
        self.user_agents = user_agents
        self.index = 0

    def get_next(self):
        ua = self.user_agents[self.index % len(self.user_agents)]
        self.index += 1
        return ua

class UsernameGenerator:
    def __init__(self, length, mode='random', chars=string.ascii_lowercase + string.digits):
        self.length = length
        self.mode = mode
        self.chars = chars
        if mode == 'systematic':
            self.product_iter = product(chars, repeat=length)
        else:
            self.generated = set()

    def next(self):
        if self.mode == 'systematic':
            try:
                return ''.join(next(self.product_iter))
            except StopIteration:
                return None
        else:
            while True:
                username = ''.join(random.choice(self.chars) for _ in range(self.length))
                if username not in self.generated:
                    self.generated.add(username)
                    return username
                if len(self.generated) >= len(self.chars) ** self.length:
                    return None

class ProxyRotator:
    def __init__(self, proxy_list=None):
        self.proxies = proxy_list if proxy_list else []
        self.index = 0

    def get_next(self):
        if not self.proxies:
            return None
        proxy = self.proxies[self.index % len(self.proxies)]
        self.index += 1
        return {'http': proxy, 'https': proxy}

def check_username(session, username, birthday, ua_rotator, proxy_rotator):
    url = f'https://auth.roblox.com/v1/usernames/validate'
    params = {
        'request.username': username,
        'request.birthday': birthday
    }
    headers = {
        'User-Agent': ua_rotator.get_next(),
        'Accept': 'application/json',
    }
    proxies = proxy_rotator.get_next()
    try:
        response = session.get(url, params=params, headers=headers, proxies=proxies, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        code = data.get('code')
        if code == 0:
            return True
        else:
            return False
    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            logger.warning("Rate limited (429). Consider increasing delay or using proxies.")
        elif response.status_code == 403:
            logger.error("Access forbidden (403). Your IP may be blocked.")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Roblox username checker (educational)')
    parser.add_argument('-n', '--names', type=int, default=DEFAULT_NAMES,
                        help='Number of valid usernames to find')
    parser.add_argument('-l', '--length', type=int, default=DEFAULT_LENGTH,
                        help='Length of usernames to generate')
    parser.add_argument('-b', '--birthday', default=DEFAULT_BIRTHDAY,
                        help='Birthday for validation (YYYY-MM-DD)')
    parser.add_argument('-o', '--output', default=DEFAULT_OUTPUT_FILE,
                        help='Output file for valid usernames')
    parser.add_argument('-d', '--delay', type=float, default=DEFAULT_DELAY,
                        help='Delay between requests in seconds')
    parser.add_argument('--mode', choices=['random', 'systematic'], default='random',
                        help='Username generation mode')
    parser.add_argument('--proxies', nargs='+',
                        help='List of proxies (e.g., http://user:pass@ip:port)')
    parser.add_argument('--user-agents', nargs='+',
                        help='List of custom user agents (space separated)')
    parser.add_argument('--max-retries', type=int, default=DEFAULT_MAX_RETRIES,
                        help='Maximum retries per request')
    parser.add_argument('--backoff-factor', type=float, default=DEFAULT_BACKOFF_FACTOR,
                        help='Backoff factor for retries')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT,
                        help='Request timeout in seconds')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable debug logging')
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    session = create_session(retries=args.max_retries, backoff_factor=args.backoff_factor)
    ua_rotator = UserAgentRotator(args.user_agents if args.user_agents else DEFAULT_USER_AGENTS)
    proxy_rotator = ProxyRotator(args.proxies)
    generator = UsernameGenerator(args.length, mode=args.mode)
    found = 0
    total_attempts = 0
    consecutive_errors = 0
    logger.info(f"Starting search for {args.names} valid {args.length}-character usernames")
    logger.info(f"Mode: {args.mode}, Delay: {args.delay}s, Proxies: {len(args.proxies) if args.proxies else 0}")
    logger.info(f"Output file: {args.output}")
    try:
        while found < args.names:
            username = generator.next()
            if username is None:
                logger.warning("Exhausted all possible usernames.")
                break
            total_attempts += 1
            try:
                available = check_username(session, username, args.birthday, ua_rotator, proxy_rotator)
                if available:
                    found += 1
                    with open(args.output, 'a+') as f:
                        f.write(f"{username}\n")
                    print(f"{bcolors.OKBLUE}[{found}/{args.names}] [+] Found: {username}{bcolors.ENDC}")
                else:
                    if args.verbose:
                        print(f"{bcolors.FAIL}[-] {username} is taken{bcolors.ENDC}")
                    else:
                        print(f"{bcolors.GRAY}[-] {username} taken{bcolors.ENDC}", end='\r')
                consecutive_errors = 0
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    wait = 2 ** consecutive_errors
                    logger.warning(f"Rate limited. Waiting {wait}s before retrying...")
                    time.sleep(wait)
                    consecutive_errors += 1
                    continue
                elif e.response.status_code == 403:
                    logger.error("Blocked by Roblox. Consider changing IP or stopping.")
                    break
                else:
                    logger.error(f"HTTP error: {e}")
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= args.max_retries:
                    logger.error("Too many consecutive errors. Exiting.")
                    break
                time.sleep(args.delay * 2)
                continue
            time.sleep(args.delay)

    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        logger.info(f"Finished. Found {found} valid usernames out of {total_attempts} attempts.")
        if found > 0:
            print(f"{bcolors.OKBLUE}[!] Results saved to {args.output}{bcolors.ENDC}")

if __name__ == '__main__':
    main()
