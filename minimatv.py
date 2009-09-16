#!/usr/bin/env python

# Copyright 2009  Carlos Corbacho <carlos@strangeworlds.co.uk>

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import sys
import time

import lxml.etree

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import QtXmlPatterns


class TVGuide(QtGui.QMainWindow):

    def __init__(self, parent=None):
        super(TVGuide, self).__init__(parent)
        self._tv_xml = None
        self.setup_widgets()
        self._populate_channel_list()

    def setup_widgets(self):
        hbox = QtGui.QHBoxLayout()
        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self._channel_list = QtGui.QTableWidget()
        self._channel_list.setColumnCount(2)
        self._channel_list.setColumnHidden(0, True)
        self._channel_list.horizontalHeader().setVisible(False)
        self._channel_list.verticalHeader().setVisible(False)
        self._schedule_table = QtGui.QTableWidget()
        self._schedule_table.setColumnCount(4)
        self._schedule_table.setHorizontalHeaderLabels([
                "Time", "Show", "Duration", "Channel"])
        self.connect(
            self._channel_list,
            QtCore.SIGNAL("cellDoubleClicked(int, int)"),
            self._switch_channel)
        splitter.addWidget(self._channel_list)
        splitter.addWidget(self._schedule_table)
        self.setCentralWidget(splitter)

    def get_tv_xml(self):
        if self._tv_xml is None:
            self._tv_xml = lxml.etree.parse("tv.xml").getroot()
        return self._tv_xml

    def _populate_channel_list(self):
        channels = self.get_tv_xml().findall("channel")
        for row, channel in enumerate(channels):
            channel_name = channel.find("display-name").text
            channel_id = channel.get("id")
            self._channel_list.insertRow(row)
            self._channel_list.setItem(
                row,
                0, QtGui.QTableWidgetItem(channel_id))
            self._channel_list.setItem(
                row,
                1, QtGui.QTableWidgetItem(channel_name))

    def _delta_from_offset(self, offset):
        # Yes, Martha, apparently there really is no simple way to
        # parse UTC offsets - see footnotes of 'time' module
        sign = offset[0]
        offset_hours_in_minutes = int(offset[1:3]) * 60
        offset_minutes = int(offset[3:5])
        offset_in_minutes = int(
            "%s%d" % (sign, offset_hours_in_minutes + offset_minutes))
        return datetime.timedelta(minutes=offset_in_minutes)

    def _utc_from_timestamp(self, full_timestamp):
        timestamp, offset = full_timestamp.split(" ")
        dt = datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        return dt - self._delta_from_offset(offset)

    def _switch_channel(self, row, column):
        channel = unicode(self._channel_list.item(row, 0).text())
        pretty_channel = unicode(self._channel_list.item(row, 1).text())
        programmes = self.get_tv_xml().xpath(
            "//programme[@channel='%s']" % channel)
        self._schedule_table.clear()
        # Erm... why?
        self._schedule_table.setHorizontalHeaderLabels([
                "Time", "Show", "Duration", "Channel"])
        now = datetime.datetime.utcnow()
        today = datetime.date.today()
        for programme in programmes:
            title = programme.find("title").text
            stop = programme.get("stop")
            stop_time = self._utc_from_timestamp(stop)
            if stop_time < now:
                continue
            start = programme.get("start")
            start_time = self._utc_from_timestamp(start)
            row = self._schedule_table.rowCount()
            duration = stop_time - start_time
            self._schedule_table.insertRow(row)
            # TODO - convert this to local time... somehow
            self._schedule_table.setItem(
                row, 0, QtGui.QTableWidgetItem(start_time.strftime("%H:%M")))
            self._schedule_table.setItem(
                row, 1, QtGui.QTableWidgetItem(title))
            self._schedule_table.setItem(
                row, 2, QtGui.QTableWidgetItem(str(duration)))
            self._schedule_table.setItem(
                row, 3, QtGui.QTableWidgetItem(pretty_channel))
        self._schedule_table.sortItems(1)
        self._schedule_table.resizeColumnsToContents()


def main():
    app = QtGui.QApplication(sys.argv)
    guide = TVGuide()
    guide.show()
    app.exec_()


if __name__ == "__main__":
    main()
