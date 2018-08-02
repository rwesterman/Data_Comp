import pandas as pd
import datetime
import logging


class Cleanup():
    def __init__(self, path):
        self.path = path
        self.df = pd.read_csv(path, encoding="ISO-8859-1", skipfooter=1, index_col=False)
        self.count_hours = 0
        # prev_minute will hold minute value of previous time string in append_hour, since it is altered element-wise
        self.prev_minute = "00"

    def output_csv(self):
        self.df.to_csv(self.path, index=False)

    def output_test_csv(self):
        self.df.to_csv("{}_test.csv".format(self.path[:-4]), index=False)

    def split_brackets(self):
        cols = self.df.columns
        new_cols = []
        for col in cols:
            new_cols.append(col.split(" [")[0])
        self.df.columns = new_cols

    def standardize_drive_temp(self):
        cols = self.df.columns
        new_cols = []
        for col in cols:
            new_cols.append(col.split(" (")[0])

        self.df.columns = new_cols

    def drop_unnamed(self):
        """Drop all columns that contain unnamed in their title"""
        unnamed = [x for x in self.df.columns if "unnamed" in x.lower()]
        self.df = self.df.drop(unnamed, axis=1)


    def fix_time(self, start_time):
        """
        This method is meant to fix SMART data that did not log the hour in its time measurement. It takes a start_time
        argument and appends it to every element in the Time column
        :param start_time: integer value between 0 and 23
        :return: returns dataframe with updated Time column
        """

        logging.debug("Trying to append hour to SMART data for file {}".format(self.path))

        # reset count_hours so there are no issues
        self.count_hours = 0
        self.df["Time"] = self.df["Time"].apply(self.append_hour, start_time=start_time)
        self.df.to_csv(self.path, index=False)

    def append_hour(self, time_string, start_time):
        logging.debug("Timestring = {}, start_time = {}".format(time_string, start_time))
        # Check to see if the string already has an Hour value
        try:
            # Remove decimal portion of time string
            time_string = time_string.split('.')[0]
            # Check that the data fits the "Minute:Second" format first
            datetime.datetime.strptime(time_string, "%M:%S")
            logging.debug("Appending Hour to Time data")

            # Get the minute value of the time string
            minute = time_string.split(":")[0]
            # If the previous minute was 59 and the new minute is 0, that means an hour has passed, so increment count_hours
            if self.prev_minute == "59" and minute == "00":
                self.count_hours += 1

            # update prev_minute to reflect the current minute so next element is updated
            self.prev_minute = minute

            # convert the hour to a zero-padded string
            hour = start_time + self.count_hours
            if hour < 10:
                hour = "0{}".format(hour)
            elif hour > 23:
                hour = "00"
            else:
                hour = str(hour)

            # update time with start_time plus however many hours have passed
            return "{}:{}".format(hour, time_string)

        except ValueError as e:
            # If it doesn't fit the Minute:Second format, then we assume the data is correct and return it as-is
            # logging.debug("Time String doesn't match %M:%S, skipping append_hour()")
            return time_string.split('.')[0]
