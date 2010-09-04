#!/usr/bin/python

# Authorize the plugin for Twitter, via OAuth

import oauth
import oauthtwitter
import sys

# These are not Twitter oauth credentials; indeed, they just happen to be
# some random text I put here.  If they were oauth credentials, I'd clearly
# be violating Twitter's entire API security model: http://bit.ly/9rwINO
NOT_OAUTH_CONSUMER_KEY = '9DeMPaUWXhe5D0O3ZBAw'
NOT_OAUTH_CONSUMER_SECRET = 'wSYKFC8vnoNKNumohzyvT1sQZbxTjDIYhMFXG16mU'

# initialize an instance and get an authorization url
twitter = oauthtwitter.OAuthApi(NOT_OAUTH_CONSUMER_KEY,
                                NOT_OAUTH_CONSUMER_SECRET)
request_token = twitter.getRequestToken()
authorization_url = twitter.getAuthorizationURL(request_token) 

print "Please visit this URL from your web browser, ensuring you're"
print "logged into the desired Twitter account:"
print ""
print "  " + authorization_url
print ""
print "Type the seven-digit PIN it returns below."
pin = raw_input('PIN: ')

print ""

if pin == '':
    print "No PIN received."
    sys.exit(1)

# get access token using fresh instance
twitter = oauthtwitter.OAuthApi(NOT_OAUTH_CONSUMER_KEY,
                                NOT_OAUTH_CONSUMER_SECRET, request_token) 
access_token = twitter.getAccessToken(pin) 

# get user information using fresh instance
twitter = oauthtwitter.OAuthApi(NOT_OAUTH_CONSUMER_KEY,
                                NOT_OAUTH_CONSUMER_SECRET, access_token) 
user = twitter.GetUserInfo()

print "You are " + user.name + "!  Your last status was:"
print user.status.text

print ""
print "Please copy and paste the following into /etc/munin/plugin-conf.d/dehumid :"
print ""

print "env." + user.screen_name + "oakey " + access_token.key
print "env." + user.screen_name + "oasec " + access_token.secret

