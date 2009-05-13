import cgi
import httplib
import inspect
import logging
import urllib
import urlparse

import httplib2
from oauth import oauth

__all__ = ('OAuthAuthentication', 'OAuthHttp')

log = logging.getLogger('oauthclient')


class OAuthAuthentication(httplib2.Authentication):

    """An httplib2 Authentication module that provides OAuth authentication.

    The OAuth authentication will be tried automatically, but to use OAuth
    authentication with a particular user agent (`Http` instance), it must
    have the OAuth consumer and access token set as one of its sets of
    credentials. For instance:

    >>> csr = oauth.OAuthConsumer(key='blah', secret='moo')
    >>> token = get_access_token_for(user)
    >>> http.add_credentials(csr, token)

    """

    def request(self, method, request_uri, headers, content):
        """Add the HTTP Authorization header to the headers for this request.

        In this implementation, the Authorization header contains the OAuth
        signing information and signature.

        """
        # TODO: wtf, have to rebuild uri from partial uri and host?
        partial_uri = urlparse.urlsplit(request_uri)
        scheme = getattr(self.http, 'default_scheme', 'http')
        uri = urlparse.urlunsplit((scheme, self.host) + partial_uri[2:])

        csr, token = self.credentials
        assert token.secret is not None

        req = oauth.OAuthRequest.from_consumer_and_token(csr, token,
            http_method=method, http_url=uri)

        sign_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
        req.set_parameter('oauth_signature_method', sign_method.get_name())
        log.debug('Signing base string %r for web request %s'
            % (sign_method.build_signature_base_string(req, csr, token),
               request_uri))
        req.sign_request(sign_method, csr, token)

        headers.update(req.to_header())


if 'oauth' not in httplib2.AUTH_SCHEME_CLASSES:
    httplib2.AUTH_SCHEME_CLASSES['oauth'] = OAuthAuthentication
if 'oauth' not in httplib2.AUTH_SCHEME_ORDER:
    httplib2.AUTH_SCHEME_ORDER[0:0] = ('oauth',)  # unshift onto front


class OAuthHttp(httplib2.Http):

    """HTTP user agent for interacting with OAuth resources.

    This `httplib2.Http` subclass has many additional methods for performing
    the consumer -> access token OAuth request cycle. It also preauthorizes
    OAuth credentials added for a given domain, so they will be used even on
    the first request.

    The OAuth request cycle has three steps to get you from a consumer key to
    an access token privileged to access the user's juicy delicious protected
    resources from the service provider:

    * Ask the service provider for a request token
    * Have the live user authorize your request token
    * Exchange your newly authorized request token for an access token

    These are accomplished through the `fetch_request_token()`,
    `authorize_token()`, and `fetch_access_token()` methods respectively.

    """

    def add_credentials(self, name, password, domain=""):
        super(OAuthHttp, self).add_credentials(name, password, domain)
        log.debug("Setting credentials for name %s password %s"
            % (name, password))
        if isinstance(name, oauth.OAuthConsumer) and domain:
            scheme = getattr(self, 'default_scheme', 'http')
            # Preauthorize these credentials for any request at that domain.
            cred = (name, password)
            domain = domain.lower()
            auth = OAuthAuthentication(cred, domain,
                "%s://%s/" % (scheme, domain), {}, None, None, self)
            self.authorizations.append(auth)

    def _sign_request(self, req, sign_method):
        req.set_parameter('oauth_signature_method', sign_method.get_name())
        # We won't have a token when fetching a request token the first time.
        token = getattr(self, 'token', None)
        if log.isEnabledFor(logging.DEBUG):
            callername = inspect.stack()[1][3]
            sbs = sign_method.build_signature_base_string(req, self.consumer,
                                                          token)
            log.debug('Signing base string %r in %s()', sbs, callername)
        req.sign_request(sign_method, self.consumer, token)

    def fetch_request_token(self):
        """Asks the service provider for a request token, returning a
        representative `oauth.OAuthToken` instance.

        This is step 1. Use the request token acquired in this step to acquire
        an authorized access token for protected resources.

        This `OAuthHttp` instance should have a `request_token_url` attribute
        containing the URL at which to ask for a request token.

        """
        self.clear_credentials()
        req = oauth.OAuthRequest.from_consumer_and_token(
            self.consumer,
            http_method='GET',
            http_url=self.request_token_url,
        )

        self._sign_request(req, oauth.OAuthSignatureMethod_HMAC_SHA1())
        resp, content = self.request(req.to_url(), method=req.get_normalized_http_method())
        if resp.status != 200:
            raise httplib.HTTPException('WHAT %d %s?!' % (resp.status, resp.reason))
        self.token = oauth.OAuthToken.from_string(content)
        return self.token

    def authorize_token(self):
        """Builds and returns the URL at which the live user can authorize a
        request token.

        This is step 2. After getting a request token from the service
        provider, give it to the live user with this URL. They will authorize
        your request token, which you can then exchange for an access token.

        This `OAuthHttp` instance should have `authorization_url` and
        `callback_url` attributes containing the base URL at which the live
        user will authorize your request token, and the URL at which the live
        user can confirm the authorization has happened and continue to step
        3, respectively.

        """
        req = oauth.OAuthRequest.from_token_and_callback(
            self.token,
            callback=self.callback_url,
            http_url=self.authorization_url,
        )
        return req.to_url()

    def fetch_access_token(self):
        """Asks the service provider for an access token to protective
        resources, returning a representative `oauth.OAuthToken` instance.

        This is step 3. After the live user authorizes your request token, use
        this to turn it into an access token for protected resources.

        This `OAuthHttp` instance should have an `access_token_url` attribute
        containing the URL at which to ask for an access token.

        """
        req = oauth.OAuthRequest.from_consumer_and_token(
            self.consumer,
            token=self.token,
            http_url=self.access_token_url,
        )

        self._sign_request(req, oauth.OAuthSignatureMethod_HMAC_SHA1())
        resp, content = self.request(req.to_url(), method=req.get_normalized_http_method())
        self.token = oauth.OAuthToken.from_string(content)
        return self.token


class NetflixHttp(OAuthHttp):

    request_token_url = 'http://api.netflix.com/oauth/request_token'
    access_token_url = 'http://api.netflix.com/oauth/access_token'
    authorization_url = 'https://api-user.netflix.com/oauth/login'
    callback_url = 'http://www.postbin.org/vo7quz'

    def authorize_token(self):
        ret = super(NetflixHttp, self).authorize_token()

        # Add in the OAuth consumer key argument Netflix wants.
        parts = list(urlparse.urlsplit(ret))
        quargs = cgi.parse_qs(parts[3])
        quargs = dict([(k, v[0]) for k, v in quargs.iteritems()])

        quargs['oauth_consumer_key'] = self.consumer.key
        quargs['application_name'] = 'Gopher'

        parts[3] = urllib.urlencode(quargs)
        ret = urlparse.urlunsplit(parts)
        return ret
