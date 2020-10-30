def id_seq():
    """Returns an identifier sequence, starting at 1."""
    nid = 1
    while True:
        yield nid
        nid = nid + 1
