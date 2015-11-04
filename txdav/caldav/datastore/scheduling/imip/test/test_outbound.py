##
# Copyright (c) 2008-2015 Apple Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##
from __future__ import print_function

from cStringIO import StringIO

from pycalendar.datetime import DateTime

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.trial import unittest
from twisted.web.template import Element, renderer, flattenString

from twistedcaldav.config import config
from twistedcaldav.ical import Component

from txdav.caldav.datastore.scheduling.imip.outbound import IMIPInvitationWork
from txdav.caldav.datastore.scheduling.imip.outbound import MailSender
from txdav.caldav.datastore.scheduling.imip.outbound import StringFormatTemplateLoader
from txdav.common.datastore.test.util import buildStore

from twext.enterprise.jobs.jobitem import JobItem

import email
from email.iterators import typed_subpart_iterator
import os


initialInviteText = u"""BEGIN:VCALENDAR
VERSION:2.0
METHOD:REQUEST
BEGIN:VEVENT
UID:CFDD5E46-4F74-478A-9311-B3FF905449C3
DTSTART:20200325T154500Z
DTEND:20200325T164500Z
ATTENDEE;CN=Th\xe9 Attendee;CUTYPE=INDIVIDUAL;PARTSTAT=NEEDS-ACTION;RSVP=TRU
 E:mailto:attendee@example.com
ATTENDEE;CN=Th\xe9 Organizer;CUTYPE=INDIVIDUAL;EMAIL=organizer@example.com;P
 ARTSTAT=ACCEPTED:urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A
ATTENDEE;CN=An Attendee without CUTYPE;EMAIL=nocutype@example.com;PARTSTAT=A
 CCEPTED:urn:uuid:4DB528DC-3E60-44FA-9546-2A00FCDCFFAB
ATTENDEE;EMAIL=nocn@example.com;PARTSTAT=ACCEPTED:urn:uuid:A592CF8B-4FC8-4E4
 F-B543-B2F29A7EEB0B
ORGANIZER;CN=Th\xe9 Organizer;EMAIL=organizer@example.com:urn:uuid:C3B38B00-
 4166-11DD-B22C-A07C87E02F6A
SUMMARY:testing outbound( )\\nEmbedded: Header
DESCRIPTION:awesome description with "<" and "&"
END:VEVENT
END:VCALENDAR
""".encode("utf-8")

inviteTextNoTimezone = u"""BEGIN:VCALENDAR
VERSION:2.0
METHOD:REQUEST
BEGIN:VEVENT
UID:CFDD5E46-4F74-478A-9311-B3FF905449C3
DTSTART;TZID=America/New_York:20200325T154500
DTEND;TZID=America/New_York:20200325T164500Z
ATTENDEE;CN=Th\xe9 Attendee;CUTYPE=INDIVIDUAL;PARTSTAT=NEEDS-ACTION;RSVP=TRU
 E:mailto:attendee@example.com
ATTENDEE;CN=Th\xe9 Organizer;CUTYPE=INDIVIDUAL;EMAIL=organizer@example.com;P
 ARTSTAT=ACCEPTED:urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A
ATTENDEE;CN=An Attendee without CUTYPE;EMAIL=nocutype@example.com;PARTSTAT=A
 CCEPTED:urn:uuid:4DB528DC-3E60-44FA-9546-2A00FCDCFFAB
ATTENDEE;EMAIL=nocn@example.com;PARTSTAT=ACCEPTED:urn:uuid:A592CF8B-4FC8-4E4
 F-B543-B2F29A7EEB0B
ORGANIZER;CN=Th\xe9 Organizer;EMAIL=organizer@example.com:urn:uuid:C3B38B00-
 4166-11DD-B22C-A07C87E02F6A
SUMMARY:t\xe9sting outbound( )
DESCRIPTION:awesome description with "<" and "&"
END:VEVENT
END:VCALENDAR
""".encode("utf-8")

inviteTextWithTimezone = u"""BEGIN:VCALENDAR
VERSION:2.0
METHOD:REQUEST
BEGIN:VTIMEZONE
TZID:America/New_York
X-LIC-LOCATION:America/New_York
BEGIN:STANDARD
DTSTART:18831118T120358
RDATE:18831118T120358
TZNAME:EST
TZOFFSETFROM:-045602
TZOFFSETTO:-0500
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19180331T020000
RRULE:FREQ=YEARLY;UNTIL=19190330T070000Z;BYDAY=-1SU;BYMONTH=3
TZNAME:EDT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:19181027T020000
RRULE:FREQ=YEARLY;UNTIL=19191026T060000Z;BYDAY=-1SU;BYMONTH=10
TZNAME:EST
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
BEGIN:STANDARD
DTSTART:19200101T000000
RDATE:19200101T000000
RDATE:19420101T000000
RDATE:19460101T000000
RDATE:19670101T000000
TZNAME:EST
TZOFFSETFROM:-0500
TZOFFSETTO:-0500
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19200328T020000
RDATE:19200328T020000
RDATE:19740106T020000
RDATE:19750223T020000
TZNAME:EDT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:19201031T020000
RDATE:19201031T020000
RDATE:19450930T020000
TZNAME:EST
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19210424T020000
RRULE:FREQ=YEARLY;UNTIL=19410427T070000Z;BYDAY=-1SU;BYMONTH=4
TZNAME:EDT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:19210925T020000
RRULE:FREQ=YEARLY;UNTIL=19410928T060000Z;BYDAY=-1SU;BYMONTH=9
TZNAME:EST
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19420209T020000
RDATE:19420209T020000
TZNAME:EWT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:DAYLIGHT
DTSTART:19450814T190000
RDATE:19450814T190000
TZNAME:EPT
TZOFFSETFROM:-0400
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:DAYLIGHT
DTSTART:19460428T020000
RRULE:FREQ=YEARLY;UNTIL=19660424T070000Z;BYDAY=-1SU;BYMONTH=4
TZNAME:EDT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:19460929T020000
RRULE:FREQ=YEARLY;UNTIL=19540926T060000Z;BYDAY=-1SU;BYMONTH=9
TZNAME:EST
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
BEGIN:STANDARD
DTSTART:19551030T020000
RRULE:FREQ=YEARLY;UNTIL=19661030T060000Z;BYDAY=-1SU;BYMONTH=10
TZNAME:EST
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19670430T020000
RRULE:FREQ=YEARLY;UNTIL=19730429T070000Z;BYDAY=-1SU;BYMONTH=4
TZNAME:EDT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:19671029T020000
RRULE:FREQ=YEARLY;UNTIL=20061029T060000Z;BYDAY=-1SU;BYMONTH=10
TZNAME:EST
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19760425T020000
RRULE:FREQ=YEARLY;UNTIL=19860427T070000Z;BYDAY=-1SU;BYMONTH=4
TZNAME:EDT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:DAYLIGHT
DTSTART:19870405T020000
RRULE:FREQ=YEARLY;UNTIL=20060402T070000Z;BYDAY=1SU;BYMONTH=4
TZNAME:EDT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZNAME:EDT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZNAME:EST
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:CFDD5E46-4F74-478A-9311-B3FF905449C3
DTSTART;TZID=America/New_York:20200325T154500
DTEND;TZID=America/New_York:20200325T164500Z
ATTENDEE;CN=Th\xe9 Attendee;CUTYPE=INDIVIDUAL;PARTSTAT=NEEDS-ACTION;RSVP=TRU
 E:mailto:attendee@example.com
ATTENDEE;CN=Th\xe9 Organizer;CUTYPE=INDIVIDUAL;EMAIL=organizer@example.com;P
 ARTSTAT=ACCEPTED:urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A
ATTENDEE;CN=An Attendee without CUTYPE;EMAIL=nocutype@example.com;PARTSTAT=A
 CCEPTED:urn:uuid:4DB528DC-3E60-44FA-9546-2A00FCDCFFAB
ATTENDEE;EMAIL=nocn@example.com;PARTSTAT=ACCEPTED:urn:uuid:A592CF8B-4FC8-4E4
 F-B543-B2F29A7EEB0B
ORGANIZER;CN=Th\xe9 Organizer;EMAIL=organizer@example.com:urn:uuid:C3B38B00-
 4166-11DD-B22C-A07C87E02F6A
SUMMARY:t\xe9sting outbound( )
DESCRIPTION:awesome description with "<" and "&"
END:VEVENT
END:VCALENDAR
""".encode("utf-8")

ORGANIZER = "urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A"
ATTENDEE = "mailto:attendee@example.com"
ICALUID = "CFDD5E46-4F74-478A-9311-B3FF905449C3"

class DummySMTPSender(object):

    def __init__(self):
        self.reset()
        self.shouldSucceed = True


    def reset(self):
        self.sendMessageCalled = False
        self.fromAddr = None
        self.toAddr = None
        self.msgId = None
        self.message = None


    def sendMessage(self, fromAddr, toAddr, msgId, message):
        self.sendMessageCalled = True
        self.fromAddr = fromAddr
        self.toAddr = toAddr
        self.msgId = msgId
        self.message = message
        return succeed(self.shouldSucceed)



class OutboundTests(unittest.TestCase):

    @inlineCallbacks
    def setUp(self):
        self.store = yield buildStore(self, None)
        self.directory = self.store.directoryService()
        self.sender = MailSender(
            "server@example.com", 7, DummySMTPSender(),
            language="en")

        def _getSender(ignored):
            return self.sender
        self.patch(IMIPInvitationWork, "getMailSender", _getSender)


    @inlineCallbacks
    def test_work(self):
        txn = self.store.newTransaction()
        yield txn.enqueue(
            IMIPInvitationWork,
            fromAddr=ORGANIZER,
            toAddr=ATTENDEE,
            icalendarText=initialInviteText.replace("\n", "\r\n"),
        )
        yield txn.commit()
        yield JobItem.waitEmpty(self.store.newTransaction, reactor, 60)

        txn = self.store.newTransaction()
        record = (yield txn.imipGetToken(
            ORGANIZER,
            ATTENDEE,
            ICALUID
        ))
        self.assertTrue(record is not None)
        record = (yield txn.imipLookupByToken(record.token))[0]
        yield txn.commit()
        self.assertEquals(record.organizer, ORGANIZER)
        self.assertEquals(record.attendee, ATTENDEE)
        self.assertEquals(record.icaluid, ICALUID)


    @inlineCallbacks
    def test_workFailure(self):
        self.sender.smtpSender.shouldSucceed = False

        txn = self.store.newTransaction()
        yield txn.enqueue(
            IMIPInvitationWork,
            fromAddr=ORGANIZER,
            toAddr=ATTENDEE,
            icalendarText=initialInviteText.replace("\n", "\r\n"),
        )
        yield txn.commit()
        yield JobItem.waitEmpty(self.store.newTransaction, reactor, 60)


    def _interceptEmail(
        self, inviteState, calendar, orgEmail, orgCn,
        attendees, fromAddress, replyToAddress, toAddress, language="en"
    ):
        self.inviteState = inviteState
        self.calendar = calendar
        self.orgEmail = orgEmail
        self.orgCn = orgCn
        self.attendees = attendees
        self.fromAddress = fromAddress
        self.replyToAddress = replyToAddress
        self.toAddress = toAddress
        self.language = language
        self.results = self._actualGenerateEmail(
            inviteState, calendar,
            orgEmail, orgCn, attendees, fromAddress, replyToAddress, toAddress,
            language=language)
        return self.results


    @inlineCallbacks
    def test_outbound(self):
        """
        Make sure outbound( ) stores tokens properly so they can be looked up
        """

        config.Scheduling.iMIP.Sending.Address = "server@example.com"
        self.patch(config.Localization, "LocalesDirectory", os.path.join(os.path.dirname(__file__), "locales"))
        self._actualGenerateEmail = self.sender.generateEmail
        self.patch(self.sender, "generateEmail", self._interceptEmail)

        data = (
            # Initial invite
            (
                initialInviteText,
                "CFDD5E46-4F74-478A-9311-B3FF905449C3",
                "urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A",
                "mailto:attendee@example.com",
                "new",
                "organizer@example.com",
                u"Th\xe9 Organizer",
                [
                    (u'Th\xe9 Attendee', u'attendee@example.com'),
                    (u'Th\xe9 Organizer', u'organizer@example.com'),
                    (u'An Attendee without CUTYPE', u'nocutype@example.com'),
                    (None, u'nocn@example.com'),
                ],
                u"Th\xe9 Organizer <organizer@example.com>",
                "=?utf-8?q?Th=C3=A9_Organizer_=3Corganizer=40example=2Ecom=3E?=",
                "attendee@example.com",
                "Event invitation: testing outbound( ) Embedded: Header",
            ),

            # Update
            (
                u"""BEGIN:VCALENDAR
VERSION:2.0
METHOD:REQUEST
BEGIN:VEVENT
UID:CFDD5E46-4F74-478A-9311-B3FF905449C3
DTSTART:20100325T154500Z
DTEND:20100325T164500Z
ATTENDEE;CN=Th\xe9 Attendee;CUTYPE=INDIVIDUAL;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:
 mailto:attendee@example.com
ATTENDEE;CN=Th\xe9 Organizer;CUTYPE=INDIVIDUAL;EMAIL=organizer@example.com;PAR
 TSTAT=ACCEPTED:urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A
ORGANIZER;CN=Th\xe9 Organizer;EMAIL=organizer@example.com:urn:uuid:C3B38B00-41
 66-11DD-B22C-A07C87E02F6A
SUMMARY:t\xe9sting outbound( ) *update*
END:VEVENT
END:VCALENDAR
""".encode("utf-8"),
                "CFDD5E46-4F74-478A-9311-B3FF905449C3",
                "urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A",
                "mailto:attendee@example.com",
                "update",
                "organizer@example.com",
                u"Th\xe9 Organizer",
                [
                    (u'Th\xe9 Attendee', u'attendee@example.com'),
                    (u'Th\xe9 Organizer', u'organizer@example.com')
                ],
                u"Th\xe9 Organizer <organizer@example.com>",
                "=?utf-8?q?Th=C3=A9_Organizer_=3Corganizer=40example=2Ecom=3E?=",
                "attendee@example.com",
                "=?utf-8?q?Event_update=3A_t=C3=A9sting_outbound=28_=29_*update*?=",
            ),

            # Reply
            (
                u"""BEGIN:VCALENDAR
VERSION:2.0
METHOD:REPLY
BEGIN:VEVENT
UID:DFDD5E46-4F74-478A-9311-B3FF905449C4
DTSTART:20100325T154500Z
DTEND:20100325T164500Z
ATTENDEE;CN=Th\xe9 Attendee;CUTYPE=INDIVIDUAL;EMAIL=attendee@example.com;PARTST
 AT=ACCEPTED:urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A
ORGANIZER;CN=Th\xe9 Organizer;EMAIL=organizer@example.com:mailto:organizer@exam
 ple.com
SUMMARY:t\xe9sting outbound( ) *reply*
END:VEVENT
END:VCALENDAR
""".encode("utf-8"),
                None,
                "urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A",
                "mailto:organizer@example.com",
                "reply",
                "organizer@example.com",
                u"Th\xe9 Organizer",
                [
                    (u'Th\xe9 Attendee', u'attendee@example.com'),
                ],
                "attendee@example.com",
                "attendee@example.com",
                "organizer@example.com",
                "=?utf-8?q?Event_reply=3A_t=C3=A9sting_outbound=28_=29_*reply*?=",
            ),

        )
        for (
            inputCalendar, UID, inputOriginator, inputRecipient, inviteState,
            outputOrganizerEmail, outputOrganizerName, outputAttendeeList,
            outputFrom, encodedFrom, outputRecipient, outputSubject
        ) in data:

            txn = self.store.newTransaction()
            yield self.sender.outbound(
                txn,
                inputOriginator,
                inputRecipient,
                Component.fromString(inputCalendar.replace("\n", "\r\n")),
                onlyAfter=DateTime(2010, 1, 1, 0, 0, 0)
            )
            yield txn.commit()

            msg = email.message_from_string(self.sender.smtpSender.message)
            self.assertEquals(msg["From"], encodedFrom)
            self.assertEquals(self.inviteState, inviteState)
            self.assertEquals(self.orgEmail, outputOrganizerEmail)
            self.assertEquals(self.orgCn, outputOrganizerName)
            self.assertEquals(self.attendees, outputAttendeeList)
            self.assertEquals(self.fromAddress, outputFrom)
            self.assertEquals(self.toAddress, outputRecipient)
            self.assertEquals(msg["Subject"], outputSubject)

            if UID: # The organizer is local, and server is sending to remote
                    # attendee
                txn = self.store.newTransaction()
                record = (yield txn.imipGetToken(inputOriginator, inputRecipient, UID))
                yield txn.commit()
                self.assertNotEquals(record, None)
                self.assertEquals(
                    msg["Reply-To"],
                    "server+%s@example.com" % (record.token,))

                # Make sure attendee property for organizer exists and matches
                # the CUA of the organizer property
                orgValue = self.calendar.getOrganizerProperty().value()
                self.assertEquals(
                    orgValue,
                    self.calendar.getAttendeeProperty([orgValue]).value()
                )

            else: # Reply only -- the attendee is local, and server is sending reply to remote organizer

                self.assertEquals(msg["Reply-To"], self.fromAddress)

            # Check that we don't send any messages for events completely in
            # the past.
            self.sender.smtpSender.reset()
            txn = self.store.newTransaction()
            yield self.sender.outbound(
                txn,
                inputOriginator,
                inputRecipient,
                Component.fromString(inputCalendar.replace("\n", "\r\n")),
                onlyAfter=DateTime(2021, 1, 1, 0, 0, 0)
            )
            yield txn.commit()
            self.assertFalse(self.sender.smtpSender.sendMessageCalled)


    @inlineCallbacks
    def test_tokens(self):
        txn = self.store.newTransaction()
        self.assertEquals((yield txn.imipLookupByToken("xyzzy")), [])
        yield txn.commit()

        txn = self.store.newTransaction()
        record1 = (yield txn.imipCreateToken("organizer", "attendee", "icaluid"))
        yield txn.commit()

        txn = self.store.newTransaction()
        record2 = (yield txn.imipGetToken("organizer", "attendee", "icaluid"))
        yield txn.commit()
        self.assertEquals(record1.token, record2.token)

        txn = self.store.newTransaction()
        record = (yield txn.imipLookupByToken(record1.token))[0]
        self.assertEquals(
            [record.organizer, record.attendee, record.icaluid],
            ["organizer", "attendee", "icaluid"])
        yield txn.commit()

        txn = self.store.newTransaction()
        yield txn.imipRemoveToken(record1.token)
        yield txn.commit()

        txn = self.store.newTransaction()
        self.assertEquals((yield txn.imipLookupByToken(record1.token)), [])
        yield txn.commit()


    @inlineCallbacks
    def test_mailtoTokens(self):
        """
        Make sure old mailto tokens are still honored
        """

        organizerEmail = "mailto:organizer@example.com"

        # Explictly store a token with mailto: CUA for organizer
        # (something that doesn't happen any more, but did in the past)
        txn = self.store.newTransaction()
        origRecord = (yield txn.imipCreateToken(
            organizerEmail,
            "mailto:attendee@example.com",
            "CFDD5E46-4F74-478A-9311-B3FF905449C3"
        ))
        yield txn.commit()

        inputCalendar = initialInviteText
        UID = "CFDD5E46-4F74-478A-9311-B3FF905449C3"
        inputOriginator = "urn:uuid:C3B38B00-4166-11DD-B22C-A07C87E02F6A"
        inputRecipient = "mailto:attendee@example.com"

        txn = self.store.newTransaction()
        yield self.sender.outbound(
            txn, inputOriginator, inputRecipient,
            Component.fromString(inputCalendar.replace("\n", "\r\n")),
            onlyAfter=DateTime(2010, 1, 1, 0, 0, 0))
        yield txn.commit()

        # Verify we didn't create a new token...
        txn = self.store.newTransaction()
        record = (yield txn.imipGetToken(inputOriginator, inputRecipient, UID))
        yield txn.commit()
        self.assertEquals(record, None)

        # But instead kept the old one...
        txn = self.store.newTransaction()
        record = (yield txn.imipGetToken(organizerEmail, inputRecipient, UID))
        yield txn.commit()
        self.assertEquals(record.token, origRecord.token)


    def generateSampleEmail(self, caltext=initialInviteText):
        """
        Invoke L{MailHandler.generateEmail} and parse the result.
        """
        calendar = Component.fromString(caltext)
        msgID, msgTxt = self.sender.generateEmail(
            inviteState='new',
            calendar=calendar,
            orgEmail=u"user01@localhost",
            orgCN=u"User Z\xe9ro One",
            attendees=[(u"Us\xe9r One", "user01@localhost"),
                       (u"User 2", "user02@localhost")],
            fromAddress="user01@localhost",
            replyToAddress="imip-system@localhost",
            toAddress="user03@localhost",
        )
        message = email.message_from_string(msgTxt)
        return msgID, message


    def test_generateEmail(self):
        """
        L{MailHandler.generateEmail} generates a MIME-formatted email with a
        text/plain part, a text/html part, and a text/calendar part.
        """
        msgID, message = self.generateSampleEmail()
        self.assertEquals(message['Message-ID'], msgID)
        expectedTypes = set(["text/plain", "text/html", "text/calendar"])
        actualTypes = set([
            part.get_content_type() for part in message.walk()
            if part.get_content_type().startswith("text/")
        ])
        self.assertEquals(actualTypes, expectedTypes)


    def test_generateEmail_noOrganizerCN(self):
        """
        L{MailHandler.generateEmail} generates a MIME-formatted email when
        the organizer property has no CN parameter.
        """
        calendar = Component.fromString(initialInviteText)
        _ignore_msgID, msgTxt = self.sender.generateEmail(
            inviteState='new',
            calendar=calendar,
            orgEmail=u"user01@localhost",
            orgCN=None,
            attendees=[(u"Us\xe9r One", "user01@localhost"),
                       (u"User 2", "user02@localhost")],
            fromAddress="user01@localhost",
            replyToAddress="imip-system@localhost",
            toAddress="user03@localhost",
        )
        message = email.message_from_string(msgTxt)
        self.assertTrue(message is not None)


    def test_generateEmail_noAttendeeCN(self):
        """
        L{MailHandler.generateEmail} generates a MIME-formatted email when
        the attendee property has no CN parameter.
        """
        calendar = Component.fromString(initialInviteText)
        _ignore_msgID, msgTxt = self.sender.generateEmail(
            inviteState='new',
            calendar=calendar,
            orgEmail=u"user01@localhost",
            orgCN=u"User Z\xe9ro One",
            attendees=[(None, "user01@localhost"),
                       (None, "user02@localhost")],
            fromAddress="user01@localhost",
            replyToAddress="imip-system@localhost",
            toAddress="user03@localhost",
        )
        message = email.message_from_string(msgTxt)
        self.assertTrue(message is not None)


    def test_messageID(self):
        """
        L{SMTPSender.betterMessageID} generates a Message-ID domain matching
        the L{config.ServerHostName} value.
        """
        self.patch(config, "ServerHostName", "calendar.example.com")
        msgID, message = self.generateSampleEmail()
        self.assertEquals(message['Message-ID'], msgID)
        self.assertEqual(msgID[:-1].split("@")[1], config.ServerHostName)


    def test_alwaysIncludeTimezones(self):
        """
        L{MailHandler.generateEmail} generates a MIME-formatted email with a
        text/plain part, a text/html part, and a text/calendar part.
        """
        _ignore, message = self.generateSampleEmail(inviteTextWithTimezone)
        calparts = tuple(typed_subpart_iterator(message, "text", "calendar"))
        self.assertEqual(len(calparts), 1)
        caldata = calparts[0].get_payload(decode=True)
        self.assertTrue("BEGIN:VTIMEZONE" in caldata)
        self.assertTrue("TZID:America/New_York" in caldata)

        _ignore, message = self.generateSampleEmail(inviteTextNoTimezone)
        calparts = tuple(typed_subpart_iterator(message, "text", "calendar"))
        self.assertEqual(len(calparts), 1)
        caldata = calparts[0].get_payload(decode=True)
        self.assertTrue("BEGIN:VTIMEZONE" in caldata)
        self.assertTrue("TZID:America/New_York" in caldata)


    def test_emailEncoding(self):
        """
        L{MailHandler.generateEmail} will preserve any non-ASCII characters
        present in the fields that it formats in the message body.
        """
        _ignore_msgID, message = self.generateSampleEmail()
        textPart = partByType(message, "text/plain")
        htmlPart = partByType(message, "text/html")

        plainText = textPart.get_payload(decode=True).decode(
            textPart.get_content_charset()
        )
        htmlText = htmlPart.get_payload(decode=True).decode(
            htmlPart.get_content_charset()
        )

        self.assertIn(u"Us\u00e9r One", plainText)
        self.assertIn(u'<a href="mailto:user01@localhost">Us\u00e9r One</a>',
                      htmlText)

        # The same assertion, but with the organizer's form.
        self.assertIn(
            u'<a href="mailto:user01@localhost">User Z\u00e9ro One</a>',
            htmlText)


    def test_emailQuoting(self):
        """
        L{MailHandler.generateEmail} will HTML-quote all relevant fields in the
        HTML part, but not the text/plain part.
        """
        _ignore_msgID, message = self.generateSampleEmail()
        htmlPart = partByType(message, "text/html").get_payload(decode=True)
        plainPart = partByType(message, "text/plain").get_payload(decode=True)
        expectedPlain = 'awesome description with "<" and "&"'
        expectedHTML = expectedPlain.replace("&", "&amp;").replace("<", "&lt;")

        self.assertIn(expectedPlain, plainPart)
        self.assertIn(expectedHTML, htmlPart)


    def test_stringFormatTemplateLoader(self):
        """
        L{StringFormatTemplateLoader.load} will convert a template with
        C{%(x)s}-format slots by converting it to a template with C{<t:slot
        name="x" />} slots, and a renderer on the document element named
        according to the constructor argument.
        """
        class StubElement(Element):
            loader = StringFormatTemplateLoader(
                lambda: StringIO(
                    "<test><alpha>%(slot1)s</alpha>%(other)s</test>"
                ),
                "testRenderHere"
            )

            @renderer
            def testRenderHere(self, request, tag):
                return tag.fillSlots(slot1="hello",
                                     other="world")
        result = []
        flattenString(None, StubElement()).addCallback(result.append)
        self.assertEquals(
            list(result),
            ["<test><alpha>hello</alpha>world</test>"]
        )


    def test_templateLoaderWithAttributes(self):
        """
        L{StringFormatTemplateLoader.load} will convert a template with
        C{%(x)s}-format slots inside attributes into t:attr elements containing
        t:slot slots.
        """
        class StubElement(Element):
            loader = StringFormatTemplateLoader(
                lambda: StringIO(
                    '<test><alpha beta="before %(slot1)s after">inner</alpha>'
                    '%(other)s</test>'
                ),
                "testRenderHere"
            )

            @renderer
            def testRenderHere(self, request, tag):
                return tag.fillSlots(slot1="hello",
                                     other="world")
        result = []
        flattenString(None, StubElement()).addCallback(result.append)
        self.assertEquals(
            result,
            [
                '<test><alpha beta="before hello after">'
                'inner</alpha>world</test>'
            ]
        )


    def test_templateLoaderTagSoup(self):
        """
        L{StringFormatTemplateLoader.load} will convert a template with
        C{%(x)s}-format slots into t:slot slots, and render a well-formed output
        document, even if the input is malformed (i.e. missing necessary closing
        tags).
        """
        class StubElement(Element):
            loader = StringFormatTemplateLoader(
                lambda: StringIO(
                    '<test><alpha beta="before %(slot1)s after">inner</alpha>'
                    '%(other)s'
                ),
                "testRenderHere"
            )

            @renderer
            def testRenderHere(self, request, tag):
                return tag.fillSlots(slot1="hello",
                                     other="world")
        result = []
        flattenString(None, StubElement()).addCallback(result.append)
        self.assertEquals(result,
                          ['<test><alpha beta="before hello after">'
                           'inner</alpha>world</test>'])


    def test_scrubHeader(self):

        self.assertEquals(self.sender._scrubHeader("ABC"), "ABC")
        self.assertEquals(self.sender._scrubHeader("ABC: 123\nXYZ: 456"), "ABC: 123 XYZ: 456")



def partByType(message, contentType):
    """
    Retrieve a MIME part from an L{email.message.Message} based on a content
    type.
    """
    for part in message.walk():
        if part.get_content_type() == contentType:
            return part
    raise KeyError(contentType)
