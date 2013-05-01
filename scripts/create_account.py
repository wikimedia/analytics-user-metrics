#!/usr/bin/python
# coding=utf-8

#Create default admin account
#For puppet from drdee

import argparse
import sys
sys.path.append('../')

from user_metrics.api import session


def create_user(username, password):
	u = session.APIUser(username)
	u.set_password(password)
	u.register_user()


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-u', '--username', default='admin', help='give username for usermetrics api')
	parser.add_argument('-p', '--password', default='vagrant', help='give password for user')
	args = parser.parse_args()

	create_user(args.username, args.password)
