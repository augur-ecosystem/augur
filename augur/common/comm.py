import smtplib
import boto3
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.mailgun.org"
SMTP_PORT = 587
SMTP_USERNAME = "postmaster@sandboxd61d71687b2c4094af7f13c045cae41d.mailgun.org"
SMTP_PASSWORD = "slartibartfast"

def send_email(to_addresses=(), subject="", body_text="", body_html="", from_address=''):
    """
    Send email to the given addresses using the default smtp server.
    :param from_address: A single valid email address
    :param to_addresses: One or more recipient addresses
    :param subject: The subject of the email
    :param body_text: The body of the text version of the email
    :param body_html: The body of the html version of the email
    :return:
    """
    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_address or 'swe@ua-ecm.com'
    msg['To'] = ";".join(to_addresses)

    msg.attach(MIMEText(body_text, 'plain'))

    if body_html:
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
        msg.attach(MIMEText(body_html, 'html'))

    s = smtplib.SMTP(host=SMTP_HOST, port=SMTP_PORT)
    s.login(SMTP_USERNAME, SMTP_PASSWORD)

    try:
        # sendmail function takes 3 arguments: sender's address, recipient's address
        # and message to send - here it is sent as one string.
        s.sendmail(from_address, to_addresses, msg.as_string())
        return True
    except Exception, e:
        print "Failed to send message with the following error: %s" % str(e)
        return False
