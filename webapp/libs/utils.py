import string
import random

def generate_token(size=64, caselimit=False):
	if caselimit:
		characters  = string.ascii_lowercase + string.digits
	else:
		characters  = string.ascii_uppercase + string.ascii_lowercase + string.digits
	token = ''.join(random.choice(characters) for x in range(size))
	return token
