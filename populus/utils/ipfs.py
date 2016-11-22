from urllib import parse  # TODO: python2


def create_ipfs_uri(ipfs_hash):
    return "ipfs://{0}".format(ipfs_hash)


def is_ipfs_uri(value):
    parse_result = parse.urlparse(value)
    if parse_result.scheme != 'ipfs':
        return False
    if not parse_result.netloc and not parse_result.path:
        return False

    return True


def extract_ipfs_path_from_uri(value):
    parse_result = parse.urlparse(value)

    if parse_result.netloc:
        if parse_result.path:
            return '/'.join((parse_result.netloc, parse_result.path))
        else:
            return parse_result.netloc
    else:
        return parse_result.path
