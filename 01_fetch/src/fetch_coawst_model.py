import time
import datetime
import xarray as xr
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import dask.array as da
import os
from dask.distributed import Client
import yaml
import utils

#client = Client()
#client

# import config
with open("01_fetch/params_config_fetch_coawst_model.yaml", 'r') as stream:
    config = yaml.safe_load(stream)

# set up write location data outputs
write_location = config['write_location']
s3_client = utils.prep_write_location(write_location, config['aws_profile'])
s3_bucket = config['s3_bucket']


def load_COAWST_model_run(url):
    '''
    This function is used to read a COAWST model output dataset from a THREDDS url
    and return a data array
    '''
    # load the dataset from the input THREDDS url and chunk it by
    # the ocean_time variable, which measures the time step in the dataset
    # model outputs are on a 3-hour time step
    # A chunk size of 1 was chosen, meaning that data will be split up by timestep.
    ds = xr.open_dataset(url, chunks={'ocean_time':1})
    # read in dataset as an array
    ds = xr.Dataset(ds)
    print(f'Size: {ds.nbytes / (-10**9)} GB')
    return ds

def salt_front_timeseries(combined_df, ds, river_mile_coords_filepath, run_number):
    # read river mile coordinates csv, which contains geospatial
    # information about the locations want to read data from
    # in the COAWST model
    river_mile_coords = pd.read_csv(river_mile_coords_filepath, index_col=0)

    # read in netcdf indices that we will pull data from
    target_x = np.array(river_mile_coords.iloc[:,[1]].values).squeeze()
    target_x = xr.DataArray(target_x-1, dims=["points"]) 
    target_y = np.array(river_mile_coords.iloc[:,[2]].values).squeeze()
    target_y = xr.DataArray(target_y-1,dims=["points"])
    # read in the corresponding river mile location for each point
    dist_mile = np.array(river_mile_coords.iloc[:,[0]].values).squeeze()
    dist_mile = xr.DataArray(dist_mile,dims=["points"])

    # pull the bottom-most vertical layer of the river profile
    # ranges from 0-16, with 0 being the bottom
    salt = ds.isel(s_rho=0)

    # select data points from pathway along shore
    # these points were provided by the COAWST modeling team
    salt = salt.isel(xi_rho=target_x,eta_rho=target_y)

    # assign river mile distance as a new coordinate in dataset
    salt = salt.assign_coords({'dist_mile': dist_mile})

    # model does not resolve well sometimes and only produces low values of salinity everywhere
    # we can't really tell where the salt front should be at these times
    # we want to mask these low values so they don't skew the location estimate
    salt_trusted = salt.where(salt.salt > 0.4)

    # convert salt variable to dataframe
    df = salt_trusted.salt.to_dataframe()

    # drop points index column so we only have one index (ocean_time)
    df_drop = df.droplevel(level=1).sort_index()

    # get the value closest to 0.52
    df_drop['abs_salt_diff_052'] = np.fabs(df_drop['salt'] - 0.52)
    s = df_drop.groupby(pd.Grouper(freq='H'))['abs_salt_diff_052'].transform('min').sort_index()
    df_sf = df_drop[df_drop['abs_salt_diff_052'] == s]
    df_sf.drop('abs_salt_diff_052', axis=1, inplace=True)

    # drop any rows that have more than one value for the hour still
    df_sf_first = df_sf.groupby(pd.Grouper(freq='H')).first()

    # take daily average by averaging hourly location throughout day 
    df_mean = df_sf_first.resample('1D').mean()

    # rename datetime column
    df_mean.reset_index(inplace=True)
    df_mean.rename({'ocean_time':'datetime'}, axis=1, inplace=True)

    # initliaze or append to combinded df
    if combined_df is not None:
        combined_df = combined_df.append(df_mean)
    else:
        combined_df = df_mean.copy()

    # save locally
    saltfront_data = os.path.join('.', '01_fetch', 'out', f'salt_front_location_from_COAWST_{run_number}.csv')
    combined_df.to_csv(saltfront_data, index=False)

    # upload csv with salt front data to S3
    if write_location == 'S3':
        print('uploading to s3')
        s3_client.upload_file(saltfront_data, s3_bucket, '01_fetch/out/'+os.path.basename(saltfront_data))
    return combined_df

def main():
    # define model run
    coawst_run_name = config['coawst_run_name']
    coawst_run_info = config['coawst_run_catalog'][coawst_run_name]

    base_url = coawst_run_info['url']
    num_files = coawst_run_info['num_files']
    u = base_url.split('/')
    run_number = u[12]

    # define csv with river mile coordinates
    river_mile_coords_filepath = config['river_mile_coords_filepath']
    
    # initialize empty variable to use as combinded df
    combined_df = None
    for file_num in range(1,num_files+1):
        print(f'fetching file {file_num}/{num_files}, time:', datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'))
        # make the formatted data url and fetch data
        file_num_str = str(file_num).zfill(5)
        url = base_url.format(file_num=file_num_str)
        ds = load_COAWST_model_run(url)
        # process and append the data
        combined_df = salt_front_timeseries(combined_df, ds, river_mile_coords_filepath, run_number)

if __name__ == '__main__':
    main()
