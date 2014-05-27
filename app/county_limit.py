from utils import PARAMETERS, parse_args, execute_query


class CountyLimit(object):
    """To have everything consistent."""

    def __init__(self):
        """Set defaults."""
        self.errors = []
        self.data = []
        self.status = "OK"
        self.request = {}

    def process_request(self, request):
        """Get input, return results."""
        self.request = parse_args(request)
        self._defaults()
        self._data()
        return self._output()

    def _output(self):
        """Compile response."""
        return {
            "status": self.status,
            "request": self.request,
            "data": self.data,
            "errors": self.errors,
        }

    def _data(self):
        """Get FHA and GSE county limits."""
        qry_args = self.request.values()
        query = """
            SELECT
                gse_limit, fha_limit
            FROM
                county_limits cl
                INNER JOIN state s ON s.state_id = cl.state_id
                INNER JOIN county c ON c.county_id = cl.county_id
            WHERE
                county_name = %s
                AND state_name = %s
        """
        rows = execute_query(query, qry_args)
        if rows and rows[0]:
            self.data = [{'gse_limit': str(rows[0][0]), 'fha_limit': str(rows[0][1])}]

    def _defaults(self):
        """Set default values."""
        # doesn't really make sense here
        tmp = dict((k, v[2]) for k, v in PARAMETERS['county-limit'].iteritems())
        tmp.update(self.request)
        self.request = tmp
