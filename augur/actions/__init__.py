#
# def add_arguments(self, parser):
#
#     parser.add_argument('--output_type', dest='output_type',
#                         choices=const.OUTPUT_TYPES, action='append', type=str,
#                         help='This is the output type of the given format.  For example: wiki,file,email,etc.')
#
#     parser.add_argument('--output_format', dest='output_format',
#                         choices=const.OUTPUT_FORMATS, type=str,
#                         help='The format of the output - as in html, json, csv, etc.')
#
#     parser.add_argument('--file', dest='output_file',
#                         help='For the file output type this is the filename and path of the output file to use')
#
#     parser.add_argument('--pageid', dest='page_id',
#                         help='Used with wiki output type. This is confluence page ID to be updated.')
#
#     parser.add_argument('--recip', dest='recipients', action='append',
#                         help='Used with email output type for indicating recipient email addresses.  '
#                              'You can have multiple recip parameters')
#
#     parser.add_argument('--mailinglist',
#                         dest='mailing_list',
#                         action='append',
#                         help='The mailing list to use (one of the keys from the DISTRIBUTION_LISTS '
#                              'variable in configs/distribution_lists.py)')
from actions.engineering_report import EngineeringReportAction


def action_engineering_report(**options):
    action = EngineeringReportAction(args=options)
    action.run()