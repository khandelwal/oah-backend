import psycopg2.extras

from utils import PARAMETERS, STATE_ABBR, parse_args, execute_query


class RateChecker(object):
    """No apparent reason."""

    def __init__(self):
        """Set parameters to default values."""
        # don't know yet what those parameters are
        self.errors = []
        self.data = []
        self.status = "OK"
        self.request = {}

    def process_request(self, request):
        """The main function which processes request and returns result back."""
        self.request = parse_args(request)
        self._defaults()
        self._data()
        return self._output()

    def _output(self):
        """Compile response"""
        return {
            "status": self.status,
            "request": self.request,
            "data": self.data,
            "errors": self.errors,
        }

    def _data(self):
        """Calculate results."""
        data = []
        minltv = maxltv = float(self.request['loan_amount']) / self.request['price'] * 100

        qry_args = [self.request['loan_amount'], self.request['loan_amount'], self.request['minfico'],
                    self.request['maxfico'], minltv, maxltv, self.request['state'], self.request['loan_amount'],
                    self.request['loan_amount'], self.request['minfico'], self.request['maxfico'], minltv, maxltv,
                    self.request['state'], minltv, maxltv, self.request['minfico'], self.request['maxfico'],
                    self.request['loan_amount'], self.request['loan_amount'], self.request['state'],
                    self.request['rate_structure'].upper(), self.request['loan_term'], self.request['loan_type']]

        query = """
            SELECT
                r.Institution AS r_Institution,
--                r.StateID AS r_StateID,
--                r.LoanPurpose AS r_LoanPurpose,
--                r.PmtType AS r_PmtType,
--                r.LoanType AS r_LoanType,
--                r.LoanTerm AS r_LoanTerm,
--                r.IntAdjTerm AS r_IntAdjTerm,
                r.Lock AS r_Lock,
                r.BaseRate AS r_BaseRate,
                r.TotalPoints AS r_TotalPoints,
--                r.IO AS r_IO,
--                r.OffersAgency AS r_OffersAgency,
                r.Planid AS r_Planid,
--                r.ARMIndex AS r_ARMIndex,
--                r.InterestRateAdjustmentCap AS r_InterestRateAdjustmentCap,
--                r.AnnualCap AS r_AnnualCap,
--                r.LoanCap AS r_LoanCap,
--                r.ARMMargin AS r_ARMMargin,
--                r.AIValue AS r_AIValue,
--                l.Planid AS l_Planid,
--                l.MinLTV AS l_MinLTV,
--                l.MaxLTV AS l_MaxLTV,
--                l.MinFICO AS l_MinFICO,
--                l.MaxFICO AS l_MaxFICO,
--                l.MinLoanAmt AS l_MinLoanAmt,
--                l.MaxLoanAmt AS l_MaxLoanAmt,
                COALESCE(adjr.adjvalueR,0) AS adjvalueR,
                COALESCE(adjp.adjvalueP,0) AS adjvalueP
            FROM
                rates r
                INNER JOIN limits l ON r.planid = l.planid
                LEFT OUTER JOIN (
                    SELECT
                        planid,
                        sum(adjvalue) adjvalueR
                    FROM adjustments
                    WHERE
                        MINLOANAMT <= %s AND %s <= MAXLOANAMT
                        AND MINFICO<= %s AND MAXFICO >= %s
                        AND %s >= minltv AND %s <= maxltv
                        -- AND proptype=''
                        AND (STATE=%s or STATE = '')
                        -- AND AffectRateType='R'
                    GROUP BY planid
                )  adjr ON adjr.PlanID = r.planid
                LEFT OUTER JOIN (
                    SELECT
                        planid,
                        sum(adjvalue) adjvalueP
                    FROM adjustments
                    WHERE
                        MINLOANAMT <= %s AND %s <= MAXLOANAMT
                        AND MINFICO<= %s AND MAXFICO >= %s
                        AND %s >= minltv AND %s <= maxltv
                        -- AND proptype=''
                        AND (STATE=%s or STATE = '')
                        -- AND AffectRateType='P'
                    GROUP BY planid
                )  adjp ON adjp.PlanID = r.planid

            WHERE 1=1
                -- Limits stuff
                AND (l.minltv <= %s AND l.maxltv >= %s)
                AND (l.minfico <= %s AND l.maxfico >= %s)
                AND (l.minloanamt <= %s AND l.maxloanamt >= %s)
                AND (r.stateid=%s or r.stateid='')
                -- AND r.loanpurpose='PURCH'
                AND r.pmttype=%s
                AND r.loanterm=%s
                AND r.loantype=%s

            ORDER BY r_Institution, r_BaseRate
        """
        rows = execute_query(query, qry_args, {'cursor_factory': psycopg2.extras.RealDictCursor})
        self.data = self._calculate_results(rows)

    def _calculate_results(self, data):
        """Remove extra rows. Return rates with numbers."""
        result = {}
        for row in data:
            row['final_points'] = row['adjvaluep'] + row['r_totalpoints']
            row['final_rates'] = "%.3f" % (row['adjvaluer'] + row['r_baserate'])
            if (
                row['r_planid'] not in result or
                abs(result[row['r_planid']]['r_totalpoints']) > abs(row['r_totalpoints']) or
                (result[row['r_planid']]['r_totalpoints'] == row['r_totalpoints'] and
                 result[row['r_planid']]['r_lock'] > row['r_lock'])
            ):
                result[row['r_planid']] = row
        data = {}
        for row in result.keys():
            if result[row]['final_rates'] in data:
                data[result[row]['final_rates']] += 1
            else:
                data[result[row]['final_rates']] = 1
        return data

    def _defaults(self):
        """Set defaults, calculate intermediate values for args."""
        self._set_ficos()
        self._set_loan_amount()
        tmp = dict((k, v[2]) for k, v in PARAMETERS['rate-checker'].iteritems())
        tmp.update(self.request)
        self.request = tmp

    def _set_loan_amount(self):
        """Set loan_amount, price and downpayment values."""
        if 'loan_amount' in self.request and 'price' in self.request and 'downpayment' in self.request:
            self.request['price'] = self.request['loan_amount'] + self.request['downpayment']
        elif 'loan_amount' in self.request and 'price' not in self.request and 'downpayment' not in self.request:
            self.request['price'] = self.request['loan_amount']
            self.request['downpayment'] = 0
        elif 'loan_amount' not in self.request and 'price' in self.request:
            if 'downpayment' not in self.request:
                self.request['downpayment'] = 0
            self.request['loan_amount'] = self.request['price'] - self.request['downpayment']
        else:
            self.request['loan_amount'] = PARAMETERS['rate-checker']['loan_amount'][2]
            self.request['price'] = PARAMETERS['rate-checker']['price'][2]
            self.request['downpayment'] = PARAMETERS['rate-checker']['downpayment'][2]

    def _set_ficos(self):
        """Set minfico and maxfico values."""
        if 'minfico' not in self.request and 'maxfico' not in self.request and 'fico' in self.request:
            self.request['minfico'] = self.request['maxfico'] = self.request['fico']
            del self.request['fico']
        # only one of them is set
        elif 'minfico' in self.request and 'maxfico' not in self.request:
            self.request['maxfico'] = self.request['minfico']
        elif 'minfico' not in self.request and 'maxfico' in self.request:
            self.request['minfico'] = self.request['maxfico']
        elif 'minfico' in self.request and 'maxfico' in self.request and self.request['minfico'] > self.request['maxfico']:
            self.request['minfico'], self.request['maxfico'] = self.request['maxfico'], self.request['minfico']
