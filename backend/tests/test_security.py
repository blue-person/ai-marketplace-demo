# Import modules
from app.security import read_bearer_key


# A bearer header gives the key
def test_reads_the_key_of_a_bearer_header():
	assert read_bearer_key("Bearer mk_abc123") == "mk_abc123"


# The name of the scheme does not depend on the case
def test_reads_the_key_when_the_scheme_is_in_lowercase():
	assert read_bearer_key("bearer mk_abc123") == "mk_abc123"


# Without the header there is no key
def test_an_empty_header_gives_no_key():
	assert read_bearer_key("") is None


# Another scheme such as Basic is not a key
def test_another_scheme_gives_no_key():
	assert read_bearer_key("Basic bWs6YWJj") is None


# The scheme alone has no key
def test_the_scheme_without_a_key_gives_no_key():
	assert read_bearer_key("Bearer ") is None
	assert read_bearer_key("Bearer") is None
