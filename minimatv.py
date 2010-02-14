#!/usr/bin/env python

# Copyright 2009-2010  Carlos Corbacho <carlos@strangeworlds.co.uk>

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

import sip
sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import QtSql


class TVGuide(QtGui.QMainWindow):

    def __init__(self, parent=None):
        super(TVGuide, self).__init__(parent)
        self._tv_xml = None
        self._pretty_channels = {}
        self.setup_models()
        self.setup_widgets()
        self._populate_channel_list()

    def setup_models(self):
        self.connect_to_database()
        self.setup_schedule_database_model()

    def connect_to_database(self):
        self._db = QtSql.QSqlDatabase("QSQLITE")
        self._db.setDatabaseName("minimatv.db")
        if not self._db.open():
            # TODO - better exception for failing to open database
            print self._db.lastError().text()
            sys.exit(1)

    def setup_schedule_database_model(self):
#        self._populate_schedule_database() # TODO - don't call this on startup
        self._schedule_model = QtSql.QSqlTableModel(self, self._db)
        self._schedule_model.setTable("programmes")
        self._schedule_model.setSort(1, QtCore.Qt.AscendingOrder)
        self._schedule_model.select()
        self._schedule_model.removeColumn(0)
        self._schedule_model.removeColumn(1)
        self._schedule_model.setHeaderData(0, QtCore.Qt.Horizontal, "Time")
        self._schedule_model.setHeaderData(1, QtCore.Qt.Horizontal, "Show")
        self._schedule_model.setHeaderData(2, QtCore.Qt.Horizontal, "Duration")
        self._schedule_model.setHeaderData(3, QtCore.Qt.Horizontal, "Channel")

    def _programmes_table_exists(self, query):
        query.exec_("""\
SELECT name FROM sqlite_master
WHERE type = 'table' AND name = 'programmes'""")
        exists = query.size() == 1
        query.finish()
        return exists

    def _create_database(self, query):
        query.exec_("""\
CREATE TABLE programmes (
id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
start VARCHAR(19) NOT NULL,
stop VARCHAR(19) NOT NULL,
title VARCHAR(200) NOT NULL,
duration VARCHAR(6) NOT NULL,
channel VARCHAR(40) NOT NULL)
""")
        query.finish()

    def _populate_schedule_entry(self, query, start, stop, title, duration, channel):
        query.bindValue(
            ":start",
            start)
        query.bindValue(
            ":stop",
            stop.strftime("%Y-%m-%d %H:%M"))
        query.bindValue(":title", title)
        query.bindValue(":duration", str(duration))
        query.bindValue(":channel", channel)
        query.exec_()

    def _populate_schedule_database(self):
        progress = QtGui.QProgressDialog(
            "Updating schedule listings...", "Cancel", 0, 0, self)
        progress.setModal(True)
        progress.show()
        query = QtSql.QSqlQuery(self._db)
        if not self._programmes_table_exists(query):
            self._create_database(query)
        query.prepare("""\
INSERT INTO programmes (start, stop, title, duration, channel)
VALUES (:start, :stop, :title, :duration, :channel)""")
        programmes = self.get_tv_xml().findall("programme")
        now = datetime.datetime.utcnow()
        for programme in programmes:
            QtGui.QApplication.processEvents()
            title = programme.find("title").text
            channel = programme.get("channel")
            stop = programme.get("stop")
            stop_time = self._utc_from_timestamp(stop)
            if stop_time < now:
                continue
            start = programme.get("start")
            start_time = self._utc_from_timestamp(start)
            duration = stop_time - start_time
            self._populate_schedule_entry(
                query, start_time, stop_time, title, duration, channel)
        query.finish()
        # TODO - hammer to crack a nut. Is this really necessary?
        self.setup_schedule_database_model()
        self._schedule_table.setModel(self._schedule_model)
        progress.hide()

    def setup_schedule_panel_widgets(self):
        self._schedule_table = QtGui.QTableView()
        self._schedule_table.setModel(self._schedule_model)
        self._schedule_table.resizeRowsToContents()
        schedule_details_group = QtGui.QGroupBox("Details:")
        schedule_details_layout = QtGui.QVBoxLayout()
        self._schedule_details = QtGui.QTextEdit()
        self._schedule_details.setReadOnly(True)
        schedule_info_grid = QtGui.QGridLayout()
        label1 = QtGui.QLabel("Show:")
        label2 = QtGui.QLabel("The Show")
        label3 = QtGui.QLabel("Time:")
        label4 = QtGui.QLabel("The Time")
        schedule_info_grid.addWidget(label1, 0, 0)
        schedule_info_grid.addWidget(label2, 0, 1)
        schedule_info_grid.addWidget(label3, 1, 0)
        schedule_info_grid.addWidget(label4, 1, 1)
        sched_info_widget = QtGui.QWidget()
        sched_info_widget.setLayout(schedule_info_grid)
        schedule_details_layout.addWidget(sched_info_widget)
        schedule_details_layout.addWidget(self._schedule_details)
        schedule_details_group.setLayout(schedule_details_layout)
        self._schedule_splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self._schedule_splitter.addWidget(self._schedule_table)
        self._schedule_splitter.addWidget(schedule_details_group)

    def setup_menu_bar(self):
        tools_menu = self.menuBar().addMenu("&Tools")
        update_action = tools_menu.addAction("Update")
        update_action.triggered.connect(self._populate_schedule_database)

    def setup_widgets(self):
        self.setup_schedule_panel_widgets()
        self.setup_menu_bar()
        # TODO - split this up
        hbox = QtGui.QHBoxLayout()
        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self._channel_list = QtGui.QTableWidget()
        self._channel_list.setColumnCount(2)
        self._channel_list.setHorizontalHeaderLabels(["", "Channels"])
        self._channel_list.setColumnHidden(0, True)
        self._channel_list.horizontalHeader().setVisible(False)
        self._channel_list.verticalHeader().setVisible(False)
        self._channel_tab = QtGui.QTabWidget()

        self._show_list = QtGui.QTableWidget()
        self._filters_vbox = QtGui.QVBoxLayout()
        filters_splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self._categories_list = QtGui.QTreeWidget() # FIXME - WRONG!
        self._categories_list.setColumnCount(1)
        self._channel_sort_button = QtGui.QPushButton()
        self._channel_sort_button.setText("&Channel Sort Mode")
        channels_layout = QtGui.QVBoxLayout()
        channels_layout.addWidget(self._channel_list)
        channels_layout.addWidget(self._channel_sort_button)
        filters_widget = QtGui.QWidget()
        filters_widget.setLayout(channels_layout)
        self._categories_list.setHeaderLabel("Categories")
        filters_splitter.addWidget(filters_widget)
        filters_splitter.addWidget(self._categories_list)
        self._channel_tab.insertTab(0, filters_splitter, "&Filters")
        self._channel_tab.insertTab(1, self._show_list, "&Lists")
        splitter.addWidget(self._schedule_splitter)
        splitter.addWidget(self._channel_tab)
        self.setCentralWidget(splitter)

    def get_tv_xml(self):
        if self._tv_xml is None:
            self._tv_xml = lxml.etree.parse("tv.xml").getroot()
        return self._tv_xml

    def get_pretty_name_for_channel(self, channel_id):
        if channel_id not in self._pretty_channels:
        # TODO - cache this lookup
            channels = self.get_tv_xml().xpath("//channel[@id='%s']" % channel_id)
            assert len(channels) == 1
            channel = channels[0]
            self._pretty_channels[channel_id] = channel.find("display-name").text
        return self._pretty_channels[channel_id]

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
        self._channel_list.resizeRowsToContents()

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
