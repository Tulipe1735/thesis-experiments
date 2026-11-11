"""Long-program authoring transport; preserve the legacy short-decision gateway."""
import json
import time
import urllib.error
import urllib.request

from grasp_optimization.astra_gateway import AstraGateway, GatewayError, NoRedirect


class AuthorGateway(AstraGateway):
    timeout_s=180

    def request(self,route,payload=None):
        if route not in ('/models','/chat/completions','/responses'):
            raise ValueError('Unapproved gateway route')
        if not 1<=self.timeout_s<=180:
            raise ValueError('Author timeout exceeds registered maximum')
        headers={'Authorization':'Bearer '+self._key}
        raw=None
        if payload is not None:
            headers['Content-Type']='application/json'
            raw=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()
        request=urllib.request.Request(self.base_url+route,data=raw,headers=headers)
        started=time.monotonic()
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=self.timeout_s) as response:
                return json.load(response),time.monotonic()-started
        except urllib.error.HTTPError as exc:
            message=exc.read(2000).decode(errors='replace').replace(self._key,'[REDACTED]')
            raise GatewayError(exc.code,message,seconds=time.monotonic()-started,retry_after=exc.headers.get('Retry-After')) from None
        except (OSError,ValueError,urllib.error.URLError) as exc:
            raise GatewayError(None,str(exc).replace(self._key,'[REDACTED]'),seconds=time.monotonic()-started) from None
