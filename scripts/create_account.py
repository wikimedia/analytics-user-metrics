#!/usr/bin/python
# coding=utf-8

#Create default admin account
#For puppet from drdee

import argparse
from user_metrics.api.session import APIUser

def create_user(username, password):
	u = APIUser(username)
	u.set_password(password)
	u.register_user()


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-u', '--username', default='admin', help='give username for usermetrics api')
	parser.add_argument('-p', '--password', default='vagrant', help='give password for user')
	args = parser.parse_args()

	create_user(args.username, args.password)
