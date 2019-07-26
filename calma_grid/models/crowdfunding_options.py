from odoo import fields, models

OPTIONS = [
    ('inversion', 'Inversión'),
    ('riesgo', 'Riesgo'),
    ('pais', 'País'),
    ('financiacion', 'Financiación'),
    ('premium', 'Premium'),
]


class CrowdfundingOptions(models.Model):
    _name = "crowdfunding.options"
    _description = "Crowdfunding Options"

    name = fields.Char()
    crowdfunding_type = fields.Selection(
        selection=OPTIONS,
    )
    note = fields.Text()
    icon = fields.Binary()
