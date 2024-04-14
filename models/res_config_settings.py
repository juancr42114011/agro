# -*- coding: utf-8 -*-

import datetime
import logging
import re
from itertools import islice

import requests
from dateutil.relativedelta import relativedelta
from lxml import etree
from pytz import timezone

from odoo import api, fields, models
from odoo.addons.web.controllers.main import xml2json_from_elementtree
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.translate import _

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    
    currency_provider = fields.Selection(selection_add=[
            ('banguat', '[GT] Banco de Guatemala'),
        ],)
    
    def _parse_banguat_data(self, available_currencies):
        """ Bank of Guatemala
        Info: https://banguat.gob.gt/tipo_cambio/
        * SOAP URL: https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx
        * Exchange rate is expressed as 1 unit of USD converted into GTQ
        """
        available_currency_names = available_currencies.mapped('name')
        if 'GTQ' not in available_currency_names or 'USD' not in available_currency_names:
            raise UserError(_('The selected exchange rate provider requires the GTQ and USD currencies to be active.'))

        headers = {
            'Content-Type': 'application/soap+xml; charset=utf-8',
        }
        body = """<?xml version="1.0" encoding="utf-8"?>
            <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <TipoCambioDia xmlns="http://www.banguat.gob.gt/variables/ws/"/>
                </soap12:Body>
            </soap12:Envelope>
        """
        res = requests.post(
            'https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx',
            data=body,
            headers=headers,
            timeout=10
        )
        res.raise_for_status()

        xml_tree = etree.fromstring(res.content)

        rslt = {}
        date_rate = xml_tree.xpath(".//*[local-name()='VarDolar']/*[local-name()='fecha']/text()")[0]
        if date_rate:
            date_rate = datetime.datetime.strptime(date_rate, '%d/%m/%Y').date()
            rslt['GTQ'] = (1.0, date_rate)
            rate = xml_tree.xpath(".//*[local-name()='VarDolar']/*[local-name()='referencia']/text()")[0] or 0.0
            if rate:
                rate = 1.0 / float(rate)
                rslt['USD'] = (rate, date_rate)
        return rslt