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


class ScheduleItem(object):

    def __init__(self, start=None, title=None, duration=None, channel=None):
        self.start = start
        self.title = title
        self.duration = duration
        self.channel = channel


class ScheduleModel(QtCore.QAbstractTableModel):

    START, TITLE, DURATION, CHANNEL = range(4)

    ATTRIBUTE_MAP = {
        START: "start",
        TITLE: "title",
        DURATION: "duration",
        CHANNEL: "channel"}

    def __init__(self, parent=None):
        super(ScheduleModel, self).__init__(parent)
        self._items = []

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.TextAlignmentRole:
            return QtCore.QVariant(int(QtCore.Qt.AlignTop))
        if (not index.isValid() or
            not (0 <= index.row() < len(self._items))):
                return QtCore.QVariant()
        schedule_item = self._items[index.row()]
        column = index.column()
        if role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(
                getattr(schedule_item, self.ATTRIBUTE_MAP[column]))
        return QtCore.QVariant()

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.TextAlignmentRole:
            if orientation == QtCore.Qt.Horizontal:
                return QtCore.QVariant(
                    int(QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter))
            return QtCore.QVariant(
                int(QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter))
        if role != QtCore.Qt.DisplayRole:
            return QtCore.QVariant()
        if orientation == QtCore.Qt.Horizontal:
            return QtCore.QVariant(self.ATTRIBUTE_MAP[section].capitalize())
        return QtCore.QVariant(int(section + 1))

    def rowCount(self, index=QtCore.QModelIndex()):
        return len(self._items)

    def columnCount(self, index=QtCore.QModelIndex()):
        return 4

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if index.isValid() and 0 <= index.row() < len(self._items):
            column = index.column()
            # TODO - is this going to start passing QString to value?
            setattr(self._items[index.row()], self.ATTRIBUTE_MAP[column], value)
            self.emit(
                QtCore.SIGNAL(
                    "dataChanged(const QModelIndex &, const QModelIndex &)"),
                index, index)
            return True

    def insertRows(self, position, rows=1, index=QtCore.QModelIndex()):
        self.beginInsertRows(
            QtCore.QModelIndex(), position, position + rows - 1)
        for row in range(rows):
            self._items.insert(position + row, ScheduleItem())
        self.endInsertRows()

    def removeRows(self):
        # Ho hum... do I even need to care?
        raise NotImplementedError()

    def clear(self):
        raise NotImplementedError()


class TVGuide(QtGui.QMainWindow):

    def __init__(self, parent=None):
        super(TVGuide, self).__init__(parent)
        self._tv_xml = None
        self.setup_models()
        self.setup_widgets()
        self._populate_channel_list()

    def setup_models(self):
        self._schedule_model = ScheduleModel()
        # TODO - this is slow - maybe stick this in a seperate thread?
        self._populate_schedule_list()

    def _populate_schedule_list(self):
        now = datetime.datetime.utcnow()
        today = datetime.date.today()
        programmes = self.get_tv_xml().findall("programme")
        for programme in programmes:
            title = programme.find("title").text
            channel = programme.get("channel")
            stop = programme.get("stop")
            stop_time = self._utc_from_timestamp(stop)
            if stop_time < now:
                continue
            start = programme.get("start")
            start_time = self._utc_from_timestamp(start)
            row = self._schedule_model.rowCount()
            duration = stop_time - start_time
            self._schedule_model.insertRows(row)
            # TODO - convert this to local time... somehow
            self._schedule_model.setData(
                self._schedule_model.index(
                    row, self._schedule_model.START),
                start_time.strftime("%H:%M"))
            self._schedule_model.setData(
                self._schedule_model.index(
                    row, self._schedule_model.TITLE),
                title)
            self._schedule_model.setData(
                self._schedule_model.index(
                    row, self._schedule_model.DURATION),
                duration)
            # TODO - handle pretty channel names
            self._schedule_model.setData(
                self._schedule_model.index(
                    row, self._schedule_model.CHANNEL),
                channel)

    def setup_widgets(self):
        hbox = QtGui.QHBoxLayout()
        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self._channel_list = QtGui.QTableWidget()
        self._channel_list.setColumnCount(2)
        self._channel_list.setColumnHidden(0, True)
        self._channel_list.horizontalHeader().setVisible(False)
        self._channel_list.verticalHeader().setVisible(False)
        self._schedule_table = QtGui.QTableView()
        self._schedule_table.setModel(self._schedule_model)
        splitter.addWidget(self._schedule_table)
        splitter.addWidget(self._channel_list)
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


def main():
    app = QtGui.QApplication(sys.argv)
    guide = TVGuide()
    guide.show()
    app.exec_()


if __name__ == "__main__":
    main()
