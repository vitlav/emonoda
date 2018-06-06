"""
    Emonoda -- A set of tools to organize and manage your torrents
    Copyright (C) 2015  Devaev Maxim <mdevaev@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import socket
import smtplib
import email.mime.multipart
import email.mime.text
import email.header
import email.utils
import contextlib
import time

from typing import List
from typing import Dict
from typing import Union
from typing import Any

from ...optconf import Option
from ...optconf.converters import as_string_list
from ...optconf.converters import as_path_or_empty

from . import ResultsType
from . import BaseConfetti
from . import templated


# =====
class Plugin(BaseConfetti):  # pylint: disable=too-many-instance-attributes
    PLUGIN_NAME = "email"

    def __init__(  # pylint: disable=super-init-not-called,too-many-arguments
        self,
        to: str,
        cc: List[str],
        subject: str,
        sender: str,
        html: bool,
        server: str,
        port: int,
        ssl: bool,
        user: str,
        passwd: str,
        template: str,
        **kwargs: Any,
    ) -> None:

        self._init_bases(**kwargs)

        self.__to = to
        self.__cc = cc
        self.__subject = subject
        self.__sender = sender
        self.__html = html
        self.__template_path = template

        self.__server = server
        self.__port = port
        self.__ssl = ssl
        self.__user = user
        self.__passwd = passwd

    @classmethod
    def get_options(cls) -> Dict[str, Option]:
        return cls._get_merged_options({
            "to":       Option(default=["root@localhost"], type=as_string_list, help="Destination email address"),
            "cc":       Option(default=[], type=as_string_list, help="Email 'CC' field"),
            "subject":  Option(default="{source} report: you have {affected} new torrents ^_^", help="Email subject"),
            "sender":   Option(default="root@localhost", help="Email 'From' field"),
            "html":     Option(default=True, help="HTML or plaintext email body"),
            "template": Option(default="", type=as_path_or_empty, help="Mako template file name"),

            "server":   Option(default="localhost", help="Hostname of SMTP server"),
            "port":     Option(default=0, help="Port of SMTP server"),
            "ssl":      Option(default=False, help="Use SMTPS"),
            "user":     Option(default="", help="Account on SMTP server"),
            "passwd":   Option(default="", help="Passwd for account on SMTP server"),
        })

    # ===

    def send_results(self, source: str, results: ResultsType) -> None:
        msg = self.__format_message(source, results)
        retries = self._retries
        while True:
            try:
                self.__send_message(msg)
                break
            except (
                smtplib.SMTPServerDisconnected,
                smtplib.SMTPConnectError,
                smtplib.SMTPHeloError,
                socket.timeout,
            ):
                if retries == 0:
                    raise
                time.sleep(self._retries_sleep)
                retries -= 1

    # ===

    def __format_message(self, source: str, results: ResultsType) -> email.mime.multipart.MIMEMultipart:
        subject_placeholders: Dict[str, Union[str, int]] = {
            field: len(items)
            for (field, items) in results.items()
        }
        subject_placeholders["source"] = source
        return self.__make_message(
            subject=self.__subject.format(**subject_placeholders),
            body=templated(
                name=(self.__template_path if self.__template_path else "email.{ctype}.{source}.mako").format(
                    ctype=("html" if self.__html else "plain"),
                    source=source,
                ),
                built_in=(not self.__template_path),
                source=source,
                results=results,
            ),
        )

    def __make_message(self, subject: str, body: str) -> email.mime.multipart.MIMEMultipart:
        email_headers = {
            "From":    self.__sender,
            "To":      ", ".join(self.__to),
            "Date":    email.utils.formatdate(localtime=True),
            "Subject": email.header.Header(subject, "utf-8"),
        }
        if len(self.__cc) > 0:
            email_headers["CC"] = ", ".join(self.__cc)

        msg = email.mime.multipart.MIMEMultipart()
        for (key, value) in email_headers.items():
            msg[key] = value  # type: ignore

        msg.attach(email.mime.text.MIMEText(  # type: ignore
            _text=body.encode("utf-8"),
            _subtype=("html" if self.__html else "plain"),
            _charset="utf-8",
        ))
        return msg

    def __send_message(self, msg: email.mime.multipart.MIMEMultipart) -> None:
        smtp_class = (smtplib.SMTP_SSL if self.__ssl else smtplib.SMTP)
        with contextlib.closing(smtp_class(
            host=self.__server,
            port=self.__port,
            timeout=self._timeout,
        )) as client:
            if self.__user:
                client.login(self.__user, self.__passwd)  # pylint: disable=no-member
            client.send_message(msg)  # pylint: disable=no-member
