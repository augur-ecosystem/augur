import json
import os
import logging
import urllib
import urlparse

from mako import exceptions
from mako.template import Template

from pyfluence import Confluence

from augur import distribution_lists
from augur import settings
from augur.common import const, comm, serializers, Struct
from augur.integrations.uagithub import UaGithub



class AugurActionError(Exception):
    pass


class Action(object):
    report_data_json = None

    def __init__(self, args=None):
        self.uagithub = UaGithub()
        self.args = args
        self.outputs = None

    def __str__(self):
        return "UA Jira Action"

    def _get_template(self):
        """
        :return: Returns the template relative path
        """
        pass

    def supported_formats(self):
        """
        Returns the array of supported output formats
        :return: Array of OUTPUT_FORMAT_XXX strings.
        """
        return []

    def render(self, output_format):
        """
        Renders the output of the action to the given format
        :param output_format: The output format to render (one of the OUTPUT_FORMAT_XXXX constants)
        :return: Returns the output in the format
        """
        if output_format == const.OUTPUT_FORMAT_HTML:
            # noinspection PyTypeChecker
            return self._render_template(self._get_template())

        elif output_format == const.OUTPUT_FORMAT_JSON:
            return json.dumps(self.report_data_json, indent=4, cls=serializers.UaJsonEncoder)

        else:
            logging.error("Output type %s not supported" % output_format)

    def _render_template(self, tpl, data=None):
        """
        Renders the given template - assumes the <projroot>/templates directory and
        passes in the report_data_json object
        :param tpl: The filename (relative to the template directory)
        :return: The rendered template
        """
        if not data and self.report_data_json is None:
            raise Exception("Report JSON not yet retrieved")
        if data:
            self.report_data_json = data

        self.report_data_json['_jira_instance'] = settings.main.integrations.jira.instance
        template_dir = settings.main.project.augur_base_dir + "/templates"
        template_ob = Template(filename='%s/%s' % (template_dir, tpl))
        try:
            return template_ob.render(data=self.report_data_json)
        except:
            err = exceptions.html_error_template().render()
            logging.error(err)
            return False

    def validate_args(self):
        if self.args.output_type not in [const.OUTPUT_TYPE_NONE, const.OUTPUT_TYPE_STDOUT]:

            # Create recipients out of mailing lists
            if not self.args.recipients:
                self.args.recipients = []

            if not self.args.mailing_list:
                self.args.mailing_list = []
            elif not isinstance(self.args.mailing_list, list):
                self.args.mailing_list = [self.args.mailing_list]

            # take the mailing list arg and add it to the recipients list.
            for ml_name in self.args.mailing_list:
                self.args.recipients.extend(distribution_lists.DISTRIBUTION_LISTS[ml_name])

            if not self.args.output_format:
                raise AugurActionError("If you are specifying an output type then you must then specify a format")

            if const.OUTPUT_TYPE_FILE in self.args.output_type and not self.args.output_file:
                raise AugurActionError("If specifying a file output type then you must use the file argument")

            if const.OUTPUT_TYPE_WIKI in self.args.output_type and not self.args.page_id:
                raise AugurActionError("If specifying a file output type then you must use the file argument")

            if const.OUTPUT_TYPE_EMAIL in self.args.output_type and not self.args.recipients:
                raise AugurActionError(
                    "If specifying an email output type then you must use the recip argument (at least one)")

    def create_action(self):
        """
        Derived classes return an instance of an action to run
        :return: An object based on the Action class.
        """
        raise NotImplemented()

    def handle(self, **options):
        self.args = Struct(**options)
        self.validate_args()
        self.run()
        self.outputs = self.generate_outputs()

        self.write_outputs()

    def write_outputs(self):
        if not self.outputs:
            # There was no output either because the specified formats didn't match what the action could output
            #   or because the user didn't specify anything and the default (JSON) was not supported.
            logging.error("There was no output for this action")
        else:
            # iterate over the types
            if not self.args.output_type:
                self.args.output_type = [const.OUTPUT_TYPE_FILE]
            else:
                self.args.output_type = [self.args.output_type] if not isinstance(self.args.output_type,
                                                                                  list) else self.args.output_type

            for t in self.args.output_type:

                # iterate over the formats
                for fmt, out in self.outputs.iteritems():
                    if t == const.OUTPUT_TYPE_EMAIL:
                        self.output_email(str(self), fmt, out)
                    elif t == const.OUTPUT_TYPE_WIKI:
                        self.output_wiki(out)
                    elif t == const.OUTPUT_TYPE_FILE:
                        self.output_file(out, fmt)
                    elif t == const.OUTPUT_TYPE_STDOUT:
                        self.output_stdout(out, fmt)

    def generate_outputs(self):
        supported_formats = self.supported_formats()
        formats = []
        if not self.args.output_format or len(self.args.output_format) == 0:
            formats.append(const.OUTPUT_FORMAT_JSON)
            self.args.output_format = formats
        else:
            formats = [self.args.output_format] if not isinstance(self.args.output_format,
                                                                  list) else self.args.output_format
        outputs = {}
        for fmt in formats:
            if fmt in supported_formats:
                outputs[fmt] = self.render(fmt)
            else:
                if len(self.args.output_format) > 0:
                    print "Requested format %s but that output is not supported by this action. Support formats: %s" % \
                          (fmt, ','.join(supported_formats))

        return outputs

    def output_email(self, subject, fmt, out):
        """
        Sends an email for the given output
        :param subject: The subject for the email
        :param fmt: The format being output
        :param out: The text of the output
        :return: Returns true if the mail was sent, False otherwise.
        """
        if not self.args.recipients:
            logging.error("No recipient emails were specified so no email was sent")
            return False

        if fmt == const.OUTPUT_FORMAT_HTML:
            comm.send_email_aws(self.args.recipients, subject, '', out)
        else:
            comm.send_email_aws(self.args.recipients, subject, out, '')

        return True

    def output_wiki(self, out):
        """
        Sends the output to replace the contents of the given wiki page.
        :param out: The text of the output
        :return: None
        """
        if self.args.page_id:
            c = Confluence(settings.main.integrations.jira.username,
                           settings.main.integrations.jira.password, settings.main.integrations.confluence.url)
            return c.update_content(self.args.page_id, html_markup=out)
        else:
            print "No page ID was specified so could not render to the wiki"

    def output_file(self, out, fmt):
        """
        Sends the output to a file
        :param out: The text of the output
        :param fmt: One of the OUTPUT_FORMAT_XXX types
        :return: None
        """
        if self.args.output_file:
            filename = self.args.output_file

            # add the extension if there isn't one and use the format type as the extension
            name, extension = os.path.splitext(self.args.output_file)
            if not extension:
                filename += "." + fmt

            f = open(filename, 'w+')
            f.write(out)
            f.close()
        else:
            print "No output file path was given so nothing was written out"

    def output_stdout(self, out, fmt):
        """
        Sends the output to stdout
        :param out: The text of the output
        :param fmt: One of the OUTPUT_FORMAT_XXX types
        :return: None
        """
        print out

    def output_wiki_attachment(self, action_output):
        """
        Generates an attachment on a wiki page.  For this to work, the action must generate data as a dictionary that
        contains (at the top level) a 'files' key which contains all the local paths to files that should be uploaded
        to the wiki.
        :param action_output: The data generated by the action
        :return:
        """
        if not self.args.page_id:
            print "A wiki page ID was not specified so wiki attachment output type could not be completed"
        elif 'files' not in action_output:
            print "No files were specified in the action output data so no attachments could be generated"
        else:
            confluence = Confluence(settings.main.integrations.jira.username,
                                    settings.main.integrations.jira.password,
                                    settings.main.integrations.confluence.url)

            for info in action_output['files']:

                if info['file']:
                    res = confluence.add_content_attachment(info['file'], self.args.page_id)
                    if res:
                        parsed_query = urlparse.urlparse(res['_links']['download'])
                        info['url'] = "{base}{path}?{query}".format(base=settings.main.integrations.confluence.url,
                                                                    path=parsed_query.path,
                                                                    query=urllib.quote_plus(parsed_query.query))
                    else:
                        print "Failed to upload attachment for %s" % info['file']
                else:
                    print "No file was found for %s" % info['team']['full']

    def get_data(self):
        return self.report_data_json

    def get_args(self):
        return self.args

    def run(self):
        pass


class TestAction(Action):
    def __init__(self, args):
        super(TestAction, self).__init__(args)

    def __str__(self):
        return "Test Action Used For Testing"

    def _get_template(self):
        # return "velocity_report.html"
        return "test_action.html"

    def supported_formats(self):
        return [const.OUTPUT_FORMAT_JSON, const.OUTPUT_FORMAT_HTML, const.OUTPUT_FORMAT_CSV, const.OUTPUT_FORMAT_IMAGE]

    def run(self):
        self.report_data_json = {
            "data1": "Hello",
            "data2": "There",
            "data3": "You"
        }
