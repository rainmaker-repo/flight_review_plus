# gigaplot.py

# Import required libraries
import pyulog
import pandas as pd
import numpy as np
from pathlib import Path
from bokeh.plotting import figure
from bokeh.layouts import column, row
from bokeh.models import HoverTool, Select, ColumnDataSource, TextInput
from bokeh.models import LinearColorMapper, ColorBar
from bokeh.transform import transform
from bokeh.palettes import Viridis256
from bokeh.models import DatetimeTickFormatter


def ulog2masterdf(ulog_path):
    """
    Converts a list of ULog files into a master DataFrame for visualization.

    Args:
        ulog_paths (list): List of ULog file paths.

    Returns:
        pd.DataFrame: Master DataFrame containing merged data from ULog files.
    """
    master_df = pd.DataFrame()
    # base_name = ulog_paths[0].stem

    # for ulog_path in ulog_paths:
    try:
        base_name = Path(ulog_path).stem

            # Parse the ULog file
        ulog = pyulog.ULog(str(ulog_path))

        for msg in ulog.data_list:
            df = pd.DataFrame(msg.data)
            df['timestamp'] = df['timestamp'] / 1e6  # Convert timestamp to seconds
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index, unit='s').round('s')  # Round timestamps
            df_resampled = df.resample('1s').mean()  # Resample to 1-second intervals
            df_resampled.reset_index(inplace=True)

            # Prefix column names with filename and message name
            prefixed_columns = {col: f"{base_name}_{msg.name}_{col}" for col in df_resampled.columns if col != 'timestamp'}
            df_resampled.rename(columns=prefixed_columns, inplace=True)

            # Merge into the master DataFrame
            if master_df.empty:
                master_df = df_resampled
            else:
                master_df = pd.merge(master_df, df_resampled, on='timestamp', how='outer')
    except Exception as e:
        print(f"Error processing {ulog_path}: {e}")

    master_df.sort_values(by="timestamp", inplace=True)
    master_df.dropna(how="all", axis=1, inplace=True)
    return master_df


def create_gigaplot(ulog_path):
    """
    Creates a Bokeh layout for visualizing ULog data.

    Args:
        ulog_paths (list): List of ULog file paths.

    Returns:
        bokeh.layouts.row: A Bokeh layout with interactive plots and controls.
    """
    # Generate the master DataFrame
    master_df = ulog2masterdf(ulog_path)
    print("Master DataFrame created.")

    # Initialize ColumnDataSource
    source = ColumnDataSource(master_df)

    # Prepare column options for selectors
    df_columns = master_df.columns.tolist()
    continuous = [col for col in df_columns if pd.api.types.is_numeric_dtype(master_df[col])]
    discrete = [col for col in df_columns if col not in continuous]

    # Visualization parameters
    SIZES = list(range(6, 22, 3))
    COLORS = Viridis256

    # Create the figure
    def create_figure():
        x_name = x.value
        y_name = y.value

        p = figure(sizing_mode='stretch_height', x_axis_type="datetime" if x_name == 'timestamp' else "linear", tools="pan,box_zoom,hover,reset",
                   title=f"{x_name} vs {y_name}")
        p.xaxis.axis_label = x_name
        p.yaxis.axis_label = y_name
        if x_name == 'timestamp':
            p.xaxis.formatter = DatetimeTickFormatter(seconds="%H:%M:%S", minutes="%H:%M:%S")

        size_data = 9  # Default size for points

        if size.value != 'None':
            size_column = size.value
            size_data = master_df[size_column]
            size_data = (size_data - size_data.min()) / (size_data.max() - size_data.min())  # Normalize
            size_data = size_data * (max(SIZES) - min(SIZES)) + min(SIZES)  # Scale to SIZES range
            source.data['size'] = size_data
        else:
            source.data['size'] = [min(SIZES)] * len(master_df)

        color_mapper = None
        if color.value != 'None':
            color_column = color.value
            color_mapper = LinearColorMapper(palette=Viridis256, low=master_df[color_column].min(), high=master_df[color_column].max())
            source.data['color'] = master_df[color_column]

        scatter = p.scatter(
            x=x_name,
            y=y_name,
            size='size',
            source=source,
            color=transform('color', color_mapper) if color_mapper else "#31AADE",
        )

        if color_mapper:
            color_bar = ColorBar(
                color_mapper=color_mapper, 
                location=(0, 0),
            )
            p.add_layout(color_bar, 'right')

        return p

    # Update the plot based on user interaction
    def update(attr, old, new):
        layout.children[1] = create_figure()

    # Dropdown filtering logic
    def update_dropdown(attr, old, new, search_box, dropdown, all_options, always_include=None):
        search_term = search_box.value.lower()
        filtered_options = [option for option in all_options if search_term in option.lower()]
        if always_include and always_include not in filtered_options:
            filtered_options.insert(0, always_include)  # Ensure the "always_include" option is available
        dropdown.options = filtered_options

    # Create selectors with search bars for Bokeh
    x_search = TextInput(prefix="X Axis")
    x = Select(value="timestamp", options=df_columns, margin=(-5,5,15,5))
    x_search.on_change("value", lambda attr, old, new: update_dropdown(attr, old, new, x_search, x, df_columns))
    x.on_change("value", update)

    y_search = TextInput(prefix="Y Axis")
    y = Select(value=f"{Path(ulog_path).stem}_sensor_gps_altitude_msl_m", options=continuous, margin=(-5,5,15,5))
    y_search.on_change("value", lambda attr, old, new: update_dropdown(attr, old, new, y_search, y, continuous))
    y.on_change("value", update)

    color_search = TextInput(prefix="Color")
    color = Select(value=f"{Path(ulog_path).stem}_todd_sensor_therm_temp_celcius", options=["None"] + continuous, margin=(-5,5,15,5))
    color_search.on_change("value", lambda attr, old, new: update_dropdown(attr, old, new, color_search, color, ["None"] + continuous))
    color.on_change("value", update)

    size_search = TextInput(prefix="Size")
    size = Select(value="None", options=["None"] + continuous, margin=(-5,5,15,5))
    size_search.on_change("value", lambda attr, old, new: update_dropdown(attr, old, new, size_search, size, ["None"] + continuous))
    size.on_change("value", update)

    # Layout and return
    controls = column(
        column(x_search, x),
        column(y_search, y),
        column(size_search, size),
        column(color_search, color),
        width=200
    )
    layout = row(controls, create_figure())
    return layout
