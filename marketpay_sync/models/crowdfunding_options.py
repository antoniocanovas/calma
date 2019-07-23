from odoo import fields, models


class CrowdfundingOptions(models.Model):
    _name = "crowdfunding.options"
    _description = "Crowdfunding Options"

    name = fields.Char()
    crowdfunding_type = fields.Selection(
        selection=[
            ('inversion', 'Inversión'),
            ('riesgo', 'Riesgo'),
            ('pais', 'País'),
            ('financiación', 'Financiación'),
            ('premium', 'Premium'),
        ])
    note = fields.Text()
    icon = fields.Binary()
