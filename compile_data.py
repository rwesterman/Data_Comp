# To those of you reading this in the future, I'm sorry it's a mess.

import datetime
import logging
import math
import os
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

from PyQt5.QtCore import QObject, pyqtSignal, QThread

import get_filepaths
from cleanup import Cleanup
import config

# ASSUMPTIONS BEING MADE:
# 4 ambient thermocouple readings exist, no broken thermocouples.
# todo: Generalize the above for thermocouple variations
# All SMART DATA will be consistent in regards to headers found in SmartData class.

class SmartData():
    def __init__(self, path, log_q):
        # Filepath to SMART data
        self.smart_path = path
        self.log_q = log_q

        logging.debug("Reading in SMART data from csv at {}".format(self.smart_path))

        # Reading in CSV with caveats. Skipping original headers due to ugly formatting, adding "Datetime" column as combination of date and time
        # Skipping footer row that always appears on SMART data, assigning headers from above to the columns.
        self.smart_df = pd.read_csv(self.smart_path, encoding="ISO-8859-1", skiprows=0,
                                    parse_dates={"Datetime": ["Date", "Time"]}, keep_date_col=True, skipfooter=1,
                                    engine='python', index_col=False)
        logging.debug(self.smart_df.head())
        # Fix headers on all columns
        self.fix_headers()
        logging.debug(self.smart_df.head())

        # Make these datetime objects
        self.smart_df["Time"] = self.smart_df["Time"].apply(self.extract_time)
        self.smart_df["Date"] = self.smart_df["Date"].apply(self.extract_date)

        # Switch the formatting of this column from Year-Date-Month to Year-Month_Date
        self.smart_df["Datetime"] = self.smart_df["Datetime"].apply(self.switch_month_date)

    def fix_headers(self):
        """Drops unneccesary columns and fixes headers"""

        col_name_list = []
        column_names = list(self.smart_df.columns.values)

        for column in column_names:
            column = column.split(" [")
            new_col_name = column[0]
            col_name_list.append(new_col_name)

        # Rename columns
        self.smart_df.columns = col_name_list

        # Drop all unneccesary columns
        cols_to_drop = ["Drive Failure", "Drive Warning", "Drive Airflow Temperature", "Total Host Writes",
                        "Total Host Reads", "Write Total", "Read Total"]
        for col in cols_to_drop:
            try:
                self.smart_df = self.smart_df.drop(col, axis=1)
            except KeyError:
                # Don't care about KeyErrors here
                pass

    def switch_month_date(self, date_data):
        """
        Pandas seems unable to recognize my datetime formatting, so I'm switching the date and month order from the SMART data
        :param date_data: pandas.Timestamp object
        :return: date_data as a Timestamp object with correct formatting
        """
        if type(date_data) is not str:
            # Convert timestamp to string
            date_data = date_data.strftime(format="%Y-%d-%m %H:%M:%S")

        try:
            # convert string to Datetime object with proper month/date order
            date_data = datetime.strptime(date_data, "%Y-%d-%m %H:%M:%S")
        except ValueError as e:
            logging.debug("Warning: {}\nPath: {}".format(e, self.smart_path))
            date_data = datetime.strptime(date_data, "%Y-%m-%d %M:%S")

        return pd.Timestamp(date_data)

    def extract_time(self, time):
        # Seconds place is decimalized in smart data (for some reason). Drop the decimal from the number here
        time = time.split(".")[0]

        # Convert time to 24 hour clock so it matches with thermal data
        new_datetime = datetime.strptime(time, "%H:%M:%S")
        new_strtime = new_datetime.time().strftime("%H:%M:%S")

        return new_strtime

    def extract_date(self, date):
        str_date = datetime.strptime(date, "%d.%m.%Y")
        return str_date.date()

    def get_smart_df(self):
        return self.smart_df

    def __len__(self):
        return self.smart_df.shape[0]


class ThermalData():
    def __init__(self, path, log_q):
        self.therm_path = path
        self.log_q = log_q

        # self.header = ["Date", "Offset Time", "Therm0", "Therm1", "Therm2", "Therm3"]
        self._prev_minute = "00"
        self._second = 0

        # Skip the header row in case it exists
        # Set index_col to false because sometimes pandas will read in first column as index
        # usecols should limit to only the columns specified in self.header
        logging.debug("Reading in csv from {}".format(self.therm_path))
        # self.therm_df = pd.read_csv(self.therm_path, names=self.header, skiprows=1, index_col=False,
        #                             usecols=self.header)
        self.therm_df = pd.read_csv(self.therm_path, index_col=False, delimiter = "\t")

        # self.therm_df["Time"] = self.therm_df["Date"].apply(self.extract_time)
        # self.therm_df = self.therm_df.drop("Date", axis=1)
        self.therm_df = self.therm_df.drop_duplicates("Time")

        self.start_hour = self._get_starting_hour()
        self.therm_df["Time"] = self.therm_df["Time"].apply(self.convert_time)

    def _get_starting_hour(self):
        first_row = self.therm_df.iloc[1]
        # should return a single element at the first row and column Time
        time = first_row.loc["Time"]
        # time_obj = datetime.strptime(time, "%H:%M:%S")
        time_obj = datetime.strptime(time, "%I:%M:%S %p")
        return time_obj.hour

    def convert_time(self, time):
        new_format = datetime.strptime(time, "%I:%M:%S %p")
        new_time = new_format.strftime("%H:%M:%S")
        return new_time

    def extract_time(self, date):
        # Get datetime object from string, format is:
        # "month/date/Year Hour(12-hour)/minute/second AM or PM"
        try:
            new_datetime = datetime.strptime(date, "%m/%d/%Y %I:%M:%S %p")
            self._prev_minute = new_datetime.minute
        except ValueError as e:
            logging.debug("Could not match expected Datetime in thermal data. Trying other options...")

            try:
                # Check to see if the seconds place is missing. If so, add it back with new_datetime.replace()
                new_datetime = datetime.strptime(date, "%m/%d/%Y %H:%M")
                logging.debug("Recognized datetime format, new datetime is {}".format(new_datetime))

                if (new_datetime.minute != self._prev_minute) or (self._second > 59):
                    self._second = 0
                new_datetime = new_datetime.replace(second=self._second)
            except ValueError as e:
                logging.error("Datetime does not fit format %m/%d/%Y %H:%M")
                raise

        self._prev_minute = new_datetime.minute
        self._second += 2
        new_strtime = new_datetime.time().strftime("%H:%M:%S")

        return new_strtime

    def get_therm_df(self):
        return self.therm_df

    def __len__(self):
        return self.therm_df.shape[0]


class PowerData():
    def __init__(self, path_3v, path_12v, log_q):
        self.path_3v = path_3v
        self.path_12v = path_12v
        self.log_q = log_q

        logging.debug("Preparing to read in power data")
        self.df_3v = pd.read_csv(self.path_3v, sep='\t')
        self.df_12v = pd.read_csv(self.path_12v, sep='\t')
        logging.debug("Power data successfully read in...")
        # If there are more than 10000 rows in the pandas dataframe, we want to reduce that number
        # down to at most 10000 by sampling every nth row
        if self.df_3v.shape[0] > 10000:
            n = int(self.df_3v.shape[0] / 10000)
            # Resample the dataframe, keeping header row, but only keeping every nth row after that
            self.df_3v = self.df_3v.iloc[1::n, :]
            # Do the same for df_12v, since they should be the same length
            self.df_12v = self.df_12v.iloc[1::n, :]

        self.total_power_df = self.combine_power()
        self.total_power_df["Time"] = self.total_power_df["Time"].apply(self.convert_time)

    def get_df_3v(self):
        return self.df_3v

    def get_df_12v(self):
        return self.df_12v

    def combine_power(self):
        logging.debug("Combining power dataframes now")
        total_power = self.df_3v.merge(self.df_12v, how='inner', on="Time", suffixes=(" 3.3V", " 12V"))

        # MAKE SURE THESE ARE NUMERIC AND NOT STRINGS
        total_power["Power 3.3V"] = pd.to_numeric(total_power["Power 3.3V"])
        total_power["Power 12V"] = pd.to_numeric(total_power["Power 12V"])

        total_power["Total Power"] = total_power["Power 3.3V"] + total_power["Power 12V"]
        return total_power

    def get_total_power(self):
        logging.debug("Returning total_power_df")
        return self.total_power_df

    def get_max_power(self):
        """
        Finds max power in each "Power" column of dataframe
        :return: Dictionary with key equal to rail or total
        """
        max_power = {"3.3V": "", "12V": "", "Total": ""}
        max_power["3.3V"] = self.total_power_df["Power 3.3V"].max()
        max_power["12V"] = self.total_power_df["Power 12V"].max()
        max_power["Total"] = self.total_power_df["Total Power"].max()
        return max_power

    def get_median_power(self):
        """
        Finds median power in each "Power" column of dataframe
        :return: Dictionary with key equal to rail or total
        """
        med_power = {"3.3V": "", "12V": "", "Total": ""}
        med_power["3.3V"] = self.total_power_df["Power 3.3V"].median()
        med_power["12V"] = self.total_power_df["Power 12V"].median()
        med_power["Total"] = self.total_power_df["Total Power"].median()
        return med_power

    def get_std_dev_power(self):
        """
        Finds median power in each "Power" column of dataframe
        :return: Dictionary with key equal to rail or total
        """
        std_dev_power = {"3.3V": "", "12V": "", "Total": ""}
        std_dev_power["3.3V"] = self.total_power_df["Power 3.3V"].std()
        std_dev_power["12V"] = self.total_power_df["Power 12V"].std()
        std_dev_power["Total"] = self.total_power_df["Total Power"].std()
        return std_dev_power

    def write_power_csv(self):
        """
        Writes a new .csv file with combined power data
        :return: returns full path to new file
        """
        # Get the basepath of the 12v or 3.3v datafiles
        basepath = os.path.dirname(self.path_12v)
        # filename = "TotalPower_{}.csv".format(suffix)
        filename = "TotalPower.csv"
        full_path = os.path.join(basepath, filename)
        self.total_power_df.to_csv(full_path, index=False)

        return full_path

    def convert_time(self, time_data):

        # Corner case of header column
        if time_data == "Time":
            return time_data
        """Converts string to datetime with correct format, then returns datetime object"""
        new_datetime = datetime.strptime(time_data, "%I:%M:%S %p")
        new_strtime = new_datetime.time().strftime("%H:%M:%S")

        return new_strtime

    def __len__(self):
        return self.total_power_df.shape[0]


class CombinedData():
    def __init__(self, dirpath, log_q, smart_df, therm_df=None, power_df=None):
        logging.debug("Entered CombinedData() init")
        self.dirpath = dirpath
        self.log_q = log_q

        self.figsize = (24, 16)
        self.smart_df = smart_df

        # Check if therm_df and power_df were passed. If they weren't, explicitly set self.therm_df = None or self.power_df = None
        if therm_df is not None:
            self.therm_df = therm_df
        else:
            self.therm_df = None

        # Power data is optional so setting this up as None if no power data given
        if power_df is not None:
            self.power_df = power_df
        else:
            self.power_df = None

        # self.mode will hold either "Total Write Rate" or "Total Read Rate" depending on the data mode
        self.mode = 'Total Write Rate'

        # Holds y axis maximum for plots
        self.max_bw = 5000

        # Get combined dataframe
        self.comb_df = self.combine_data()

    def _get_max_bw(self):
        """Set self.max_bw to the closest ceiling value divisible by 500"""
        max_bw = self.comb_df[self.mode].max()
        self.max_bw = math.ceil(max_bw / 500.0) * 500.0

    def combine_data(self):
        """
        This performs and "inner" merge, meaning we will lose some fidelity in the data, due to times not matching up perfectly.
        This seems to be okay though.
        :return:
        """

        # Do an "inner" merge. This assumes that the Thermal data is being logged every 1 second and the smart data every 2 seconds
        if self.therm_df is not None:
            comb_df = self.therm_df.merge(self.smart_df, how="inner", on="Time")
            try:
                # Set "Ambient" column to the intake reading (the name will change depending on the chassis)
                comb_df["Ambient"] = comb_df["Rear Intake"]
            except KeyError as e:
                comb_df["Ambient"] = comb_df["Intake"]
        else:
            comb_df = self.smart_df.copy()

        # comb_df = self.therm_df.merge(self.smart_df, how = "inner", on = "Time")
        comb_df["Datetime"] = pd.to_datetime(comb_df["Datetime"], yearfirst=True,
                                             unit='s')  # format = "%Y-%d-%m %H:%M:%S",

        # If power data is available, merge it into comb_df
        # Merge on "left" because we want to keep the time data from self.comb_df
        if self.power_df is not None:
            comb_df = comb_df.merge(self.power_df, how="left", on="Time")

        comb_df = comb_df.set_index('Datetime')

        # Drop any NaN values from index
        comb_df = comb_df.loc[comb_df.index.dropna()]

        # Sometimes SMART data won't show write/read rate for the controller drive, which shifts all suffixes back one

        # Create a Total Write Rate column and populate it here
        try:
            comb_df["Total Write Rate"] = comb_df["Write Rate.1"].add(comb_df["Write Rate.2"])
            comb_df["Total Write Rate"] = comb_df["Total Write Rate"].add(comb_df["Write Rate.3"])
            comb_df["Total Write Rate"] = comb_df["Total Write Rate"].add(comb_df["Write Rate.4"])
        except KeyError as e:
            logging.debug("No Key {} for file {}. This is a known labeling issue and is already "
                          "addressed in the code".format(e, self.dirpath))

            comb_df["Total Write Rate"] = comb_df["Write Rate"].add(comb_df["Write Rate.1"])
            comb_df["Total Write Rate"] = comb_df["Total Write Rate"].add(comb_df["Write Rate.2"])
            comb_df["Total Write Rate"] = comb_df["Total Write Rate"].add(comb_df["Write Rate.3"])

        try:
            # Create a Total Read Rate column and populate it here
            comb_df["Total Read Rate"] = comb_df["Read Rate.1"].add(comb_df["Read Rate.2"])
            comb_df["Total Read Rate"] = comb_df["Total Read Rate"].add(comb_df["Read Rate.3"])
            comb_df["Total Read Rate"] = comb_df["Total Read Rate"].add(comb_df["Read Rate.4"])
        except KeyError as e:
            logging.debug("No Key {} for file {}. This is a known labeling issue and is already "
                          "addressed in the code".format(e, self.dirpath))

            comb_df["Total Read Rate"] = comb_df["Read Rate"].add(comb_df["Read Rate.1"])
            comb_df["Total Read Rate"] = comb_df["Total Read Rate"].add(comb_df["Read Rate.2"])
            comb_df["Total Read Rate"] = comb_df["Total Read Rate"].add(comb_df["Read Rate.3"])

        # Create Max Drive Temp column and populate it
        try:
            comb_df["Max Drive Temp"] = comb_df[
            ["Drive Temperature.1", "Drive Temperature.2", "Drive Temperature.3", "Drive Temperature.4"]].max(axis=1)
        except KeyError as e:
            logging.warning("KeyError {}, trying other configuration.".format(e))
            comb_df["Max Drive Temp"] = comb_df[
            ["Drive Temperature", "Drive Temperature.1", "Drive Temperature.2", "Drive Temperature.3"]].max(axis=1)

        # Explicitly convert to matplotlib mdates for correct plotting
        comb_df['mdate'] = [mdates.date2num(d) for d in comb_df.index]
        comb_df = comb_df.set_index('mdate')

        return comb_df

    def output_comb_df(self, filepath):
        try:
            self.comb_df.to_csv(filepath, index=False)
        except PermissionError as e:
            logging.error("ERROR: {}".format(e))

    def remove_outliers(self, df, col_name):
        """removes datapoints that fall outside of 3 standard deviations of the mean data."""
        new_df = df[np.abs(df[col_name] - df[col_name].mean()) <= (3 * df[col_name].std())]
        return new_df


    def plot_all(self):
        """Plots all graphs with found data"""

        # Find the max bandwidth for the plots that use secondary y-axes
        # self._get_max_bw()

        self.plot_throttle()
        self.plot_temps()

        if self.power_df is not None:
            self.plot_power()

        plt.clf()

    def plot_power(self):
        """Plot Total Power Draw vs Total Write Rate"""
        self._get_max_bw()

        # Skip power plot if data doesn't exist
        if self.power_df is None:
            return

        # For some reason, when merging the dataframes the Datetime index has lots of NaN spots.
        # These need to be dropped for this plot.

        pow_df = self.comb_df[["Total Power", self.mode]].copy()

        logging.debug("Beginning to plot power vs bandwidth")

        # Drop NaN rows from Datetime index
        pow_df = pow_df.loc[pow_df.index.dropna()]

        # Set values of 0.000 to NaN for this plot. Don't want to show zero values
        pow_df = pow_df.replace(0.000, np.NaN)

        pow_df = pow_df.dropna(how="any")

        # pow_df = pow_df.drop_duplicates(subset = pow_df.index, keep = "first")

        # Droping rows with duplicate indices
        pow_df = pow_df[~pow_df.index.duplicated(keep='first')]

        pow_df = pow_df.sort_index()

        logging.debug("pow_df manipulation successful")
        # Explicitly set the index to a datetime object so it can be plotted correctly
        # pow_df.index = pd.to_datetime(pow_df.index)

        # Setup plot options
        fig, ax1 = plt.subplots(figsize=self.figsize)
        # ax1.xaxis.set_major_formatter(mdates.AutoDateFormatter('%Y-$m-%d %H:%M:%S'))
        # ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax2 = ax1.twinx()
        ax1.plot(pow_df.index, pow_df["Total Power"], c = 'b')
        ax2.plot(pow_df.index, pow_df[self.mode], '#cc5500')

        # ax1.scatter(pow_df.index, pow_df["Total Power"], color = 'b')
        # ax2.scatter(pow_df.index, pow_df[self.mode], color = '#cc5500')
        ax1.set_ylabel("Total Power Draw (W)")
        ax2.set_ylabel("{} (MB/s)".format(self.mode))

        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc=0)

        ax2.set_ylim(0, self.max_bw)

        # fig.autofmt_xdate()

        plt.title("Total Power Draw vs {}".format(self.mode))

        # plt.show()

        save_path = os.path.join(self.dirpath, "Power_and_BW.png")
        # plt.show()

        
        # Put the message in the queue in order to print it out immediately
        self.log_q.put("Saving Power_and_Bandwidth at {}".format(save_path))
        # logging.info("Saving Power_and_Bandwidth at {}".format(save_path))

        plt.savefig(save_path, dpi='figure', format="png")

    def plot_throttle(self):
        """Plot Max NAND temperature across drives vs Total Write Rate"""

        self._get_max_bw()

        # Copy Total Rate and Max Drive Temp from comb_df
        thr_df = self.comb_df[[self.mode, "Max Drive Temp"]].copy()

        thr_df = thr_df.sort_index()

        # Setup plot options
        fig, ax1 = plt.subplots(figsize=self.figsize)

        # ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-$m-%d %H:%M:%S'))
        # ax1.xaxis.set_major_locator(mdates.HourLocator())

        ax2 = ax1.twinx()
        ax1.plot(thr_df.index, thr_df["Max Drive Temp"], 'b')
        ax2.plot(thr_df.index, thr_df[self.mode], '#cc5500')
        # ax1.scatter(thr_df.index, thr_df["Max Drive Temp"], 'b')
        # ax2.scatter(thr_df.index, thr_df[self.mode], '#cc5500')

        ax1.set_ylabel("NAND Temperature (C)")
        ax2.set_ylabel("{} (MB/s)".format(self.mode))

        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc=2)

        fig.autofmt_xdate()

        ax2.set_ylim(0, self.max_bw)

        plt.title("Drive Temperature vs {}".format(self.mode))

        save_path = os.path.join(self.dirpath, "Drive_Temp_vs_Bandwidth.png")

        

        self.log_q.put("Saving drive_temp_vs_write at {}".format(save_path))
        # logging.info("Saving drive_temp_vs_write at {}".format(save_path))

        plt.savefig(save_path, dpi='figure')

    def plot_temps(self):
        """
        Plot NAND temps vs Ambient Temp
        :return:
        """

        self._get_max_bw()

        try:
            plot_df = self.comb_df[["Drive Temperature.1", "Drive Temperature.2", "Drive Temperature.3",
                                "Drive Temperature.4", "Ambient"]].copy()
            cols_to_plot = ["Drive Temperature.1", "Drive Temperature.2", "Drive Temperature.3", "Drive Temperature.4",
                            "Ambient"]
        except KeyError as e:
            logging.warning("KeyError {}, trying other configuration.".format(e))
            plot_df = self.comb_df[["Drive Temperature", "Drive Temperature.1", "Drive Temperature.2",
                                    "Drive Temperature.3", "Ambient"]].copy()
            cols_to_plot = ["Drive Temperature", "Drive Temperature.1", "Drive Temperature.2", "Drive Temperature.3",
                            "Ambient"]



        # Drop all rows that have an NaN value
        plot_df = plot_df.dropna(axis=0, how="any")

        plot_df = plot_df.drop_duplicates()

        fig, ax1 = plt.subplots(figsize=self.figsize)

        # plot all columns in cols_to_plot
        for col in cols_to_plot:
            ax1.plot(plot_df.index, plot_df[col], label=col)
            # ax1.scatter(plot_df.index, plot_df[col], label = col)

        plt.minorticks_off()
        plt.tick_params(axis='x', which='minor', bottom=False)

        plt.grid(axis='y')
        # Set y axis ticks at every 1 degree
        ax1.yaxis.set_major_locator(ticker.MultipleLocator(1))

        ax1.set_ylabel("Temperature (C)")

        ax1.legend()

        plt.title("Drive Temperature vs Ambient Temperature")

        # plt.show()
        save_path = os.path.join(self.dirpath, "Drive_Temp_vs_Ambient.png")

        


        self.log_q.put("Saving Drive_Temp_vs_Ambient at ()".format(save_path))
        # logging.info("Saving drive_temp_vs_ambient at {}".format(save_path))
        plt.savefig(save_path, dpi='figure')

    def power_vs_bw(self):
        """Plot Total Power Draw vs Total Write Rate"""
        self._get_max_bw()

        # Skip power plot if data doesn't exist
        if self.power_df is None:
            return

        # Copy over total bandwidth (self.mode), and all power columns
        pow_df = self.comb_df[["Total Power", "Power 3.3V", "Power 12V", self.mode]].copy()

        logging.debug("Beginning to plot power vs bandwidth")

        # Store original length of dataframe for comparison of removed outliers
        orig_len = len(pow_df)
        # remove outliers (outside 3 stddev) from data
        pow_df = self.remove_outliers(pow_df, self.mode)
        pow_df = self.remove_outliers(pow_df, "Total Power")

        if orig_len - len(pow_df) > 0:
            config.dbglog.debug("Removed {} rows of data as outliers".format(orig_len - len(pow_df)))

        # Drop NaN rows from Datetime index
        pow_df = pow_df.loc[pow_df.index.dropna()]

        # Set values of 0.000 to NaN for this plot. Don't want to show zero values. Then drop these rows
        pow_df = pow_df.replace(0.000, np.NaN)
        pow_df = pow_df.dropna(how="any")

        # Droping rows with duplicate indices
        pow_df = pow_df[~pow_df.index.duplicated(keep='first')]

        # Sort the data by total bandwidth
        pow_df = pow_df.sort_values(by = self.mode)


        logging.debug("power_vs_bw manipulation successful")
        # Explicitly set the index to a datetime object so it can be plotted correctly
        # pow_df.index = pd.to_datetime(pow_df.index)

        fit = np.polyfit(pow_df[self.mode], pow_df["Total Power"], 1)
        fit_fn = np.poly1d(fit)

        # Setup plot options
        fig, ax1 = plt.subplots(figsize=self.figsize)
        #
        # # create plot with total bandwidth as X-axis and total power as Y axis
        # ax1.scatter(pow_df[self.mode], pow_df["Total Power"], c='b')
        #
        # ax1.set_ylabel("Total Power Draw (W)")
        # ax1.set_xlabel("Total Bandwidth (MB/s)")
        #
        # lines, labels = ax1.get_legend_handles_labels()
        # ax1.legend(lines, labels, loc=0)
        #
        # # fig.autofmt_xdate()

        plt.plot(pow_df[self.mode], pow_df["Total Power"], '.')
        plt.plot(pow_df[self.mode], fit_fn(pow_df[self.mode]), '-')
        plt.title("Power Draw vs Bandwidth".format(self.mode))

        # plt.show()

        save_path = os.path.join(self.dirpath, "Power_vs_Bandwidth.png")
        # plt.show()


        # Put the message in the queue in order to print it out immediately
        self.log_q.put("Saving Power_vs_Bandwidth at {}".format(save_path))
        # logging.info("Saving Power_vs_Bandwidth at {}".format(save_path))

        plt.savefig(save_path, dpi='figure', format="png")

    def __len__(self):
        """Returns number of rows in comb_df"""
        return self.comb_df.shape[0]


def bw_vs_power(smart_path, pow3_path, pow12_path, log_q):
    smart = SmartData(smart_path, log_q)
    power = PowerData(pow3_path, pow12_path, log_q)

    smart_df = smart.get_smart_df()
    power_df = power.get_total_power()

    comb_df = pd.merge(smart_df, power_df, how="inner", on="Time")
    logging.debug(comb_df.head())
    # first drop empty columns:
    comb_df = comb_df.dropna(axis=1, how="all")
    # then drop empty rows:
    comb_df = comb_df.dropna(axis=0, how="any")
    # comb_df = comb_df.sort_values(by = "Time")

    location = os.path.join(os.path.dirname(smart_path), "combined_data.csv")

    comb_df.to_csv(location, index=False)


def plot_data(log_q, plot_power=True, plot_throttle=True, plot_temps=True, dirpath=os.getcwd()):
    """Walks directories, finds all csv data, then sorts into dataframes and plots"""

    # config.loop_flag = True

    # paths holds the filepaths for each type of data
    paths = get_filepaths.get_csv_paths(dirpath)
    # paths becomes a list of dicts, where each element of the list holds a dict with direct links to full filepath for each type of data
    paths = get_filepaths.filter_data(paths)
    # logging.info("All paths here:\n{}".format(paths))
    print("plot_data q object {}".format(log_q))
    log_q.put("Running...")
    # logging.info("Running...")

    # logging.info("Running...")
    # for each "test" in paths create dataframes and plots (where a test is a particular setup ie 1085_fans_high_heaters_on_5G)
    for test in paths:

        # if test is an empty dictionary, skip that iteration
        if not test:
            continue

        logging.debug("Dataset is at {}".format(test))

        dirpath = os.path.dirname(test["smart"])

        try:
            # Check that thermal data is present
            thermal = ThermalData(test["thermal"], log_q)
            therm_df = thermal.get_therm_df()
            therm_exists = True
        except KeyError:
            # If not present, skip that iteration.
            logging.warning("The data at {} has no thermal data or is mislabled.".format(dirpath))
            therm_exists = False
            therm_df = None

        # Clean up the SMART data so it matches the expected dataframe
        cleaner = Cleanup(test["smart"])
        # Append Hour to SMART data if necessary, using thermal data's starting hour time. This should *almost* always work
        # Check that the thermal data actually exists first. NOTE: THIS MAY CAUSE ISSUES WITH POWER VS SMART DATA MATCHING IF THERMAL DATA DOESN'T EXIST
        if therm_exists:
            cleaner.fix_time(thermal.start_hour)

        cleaner.drop_unnamed()
        cleaner.split_brackets()
        cleaner.standardize_drive_temp()
        cleaner.output_csv()

        smart = SmartData(test["smart"], log_q)


        try:
            power = PowerData(test["3p3v"], test["12v"], log_q)
            power.write_power_csv()
            power_df = power.get_total_power()
        except KeyError as e:
            log_q.put("No Power data for {}".format(dirpath))
            # logging.info("No Power data for {}".format(dirpath))
            power_df = None

        # Now accounts for missing thermal data
        alldata = CombinedData(dirpath, log_q, smart.get_smart_df(), therm_df, power_df)

        # Set the mode based on SMART data
        if "read" in test["smart"].lower():
            alldata.mode = "Total Read Rate"
        else:
            alldata.mode = "Total Write Rate"

        if plot_throttle:
            alldata.plot_throttle()
        if plot_temps and therm_exists:
            alldata.plot_temps()
        if plot_power:
            alldata.plot_power()
            alldata.power_vs_bw()

        comb_data_path = os.path.join(dirpath, "Combined_Data.csv")
        log_q.put("Outputting combined data to {}".format(comb_data_path))
        # logging.info("Outputting combined data to {}".format(comb_data_path))
        alldata.output_comb_df(comb_data_path)

    log_q.put("Finished!")
    # logging.info("Finished!")


class LogThread(QThread):
    log = pyqtSignal(str)

    def __init__(self, log_q, parent = None):
        super().__init__(parent)
        self.log_q = log_q
        self._items = []

    def set_items(self, items):
        if not self.isRunning():
            # Not sure if I want this as a list
            self._items[:] = items

    def run(self):
        for item in self._items:
            self.log.emit(item)


    def thread_logger(self):
        """
        Writes log data in real-time to GUI, run on a separate thread/process
        :param log_q: a Queue object holding log message
        :return:
        """
        # if printonce:
        #     print("thread_logger q object {}".format(log_q))

        if not self.log_q.empty():
            msg = self.log_q.get()

            # None is the poison pill for this queue. It will be shutdown when it receives this message
            if msg is None:
                return False
            else:
                # logging.info(msg)
                self.log.emit(msg)
        # return True to continue the loop until the "poison-pill" code is received
        return True

