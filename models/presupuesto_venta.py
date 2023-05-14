# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

import datetime
from dateutil.relativedelta import relativedelta

from odoo.tools.misc import xlsxwriter
from xlsxwriter.utility import xl_col_to_name
import base64
import io
import logging

