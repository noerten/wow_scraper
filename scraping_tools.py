import random
def load_user_agents(uafile='user_agents.txt'):
    """
    uafile : string
        path to text file of user agents, one per line
    """
    uas = []
    with open(uafile, 'r') as uaf:
        for ua in uaf.readlines():
            if ua:
                uas.append(ua.strip()[1:-1-1])
    random.shuffle(uas)
    return uas

def load_proxies(pfile='proxy_list.txt'):
    proxies = []
    with open(pfile, 'r') as proxy_file:
        for proxy in proxy_file.readlines():
            if proxy:
                proxies.append(proxy.strip())
    random.shuffle(proxies)
    return proxies
