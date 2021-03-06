# -*- coding: utf-8 -*-
#Created on Wed Dec 22 20:58:51 2021
#@author: ggorski


import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os
import pickle
import yaml
import utils

#import config
with open("03a_it_analysis/params_config_it_analysis_data_prep.yaml", 'r') as stream:
    config = yaml.safe_load(stream)['it_analysis_data_prep.py']

###
def select_sources(srcs, date_start, date_end):
    '''select the variables you are interested in examining, 
    srcs must be a list using the exact variable names,
    it will return a list of dataframes, each dataframe corresponding to a site
    with the requested variables as columns'''
    
    print('Looking for sources: ', srcs)
    
    srcs_list = list()
    srcs_list_historical = list()
    
    date_start_pd = pd.to_datetime(date_start)
    date_end_pd = pd.to_datetime(date_end)
    
    
    files_to_read = []
    for top,dirs,files in os.walk('02_munge/out/'):
        if top == '02_munge/out/D' or top == '02_munge/out/daily_summaries':
            files_to_read.extend([os.path.join(top,files) for files in files])

    
    
    for file in files_to_read:
        #read each file
        data = pd.read_csv(file, parse_dates = True, index_col='datetime')
        col_list = set(data.columns)
        srcs_set = set(srcs)
        #if the columns of the dataframe contain any of the entries in srcs
        if len(col_list.intersection(srcs_set)) > 1: 
            #select the columns that contain the entries in srcs
            matches = list(col_list.intersection(srcs_set))
            #subset those columns
            data_col_select = data.loc[:,matches]
            #this relies on a specific file naming structure, it appends the site name to the column header
            data_col_select = data_col_select.add_suffix('_'+str(file.split('_')[-1].split('.')[0]))

            #make a copy to store for historical data
            data_col_select_historical = data_col_select[:date_end_pd.date()].copy()
            #store all the data in _historical for preprocessing
            srcs_list_historical.append(data_col_select_historical)
            #subset only the date range of interest
            data_col_select = data_col_select[date_start_pd.date():date_end_pd.date()]
            print(str(file)+' : Sources Found')
            print(matches)
            srcs_list.append(data_col_select)
        else:
            print(str(file)+' : No Data')
            continue
    return srcs_list, srcs_list_historical
    
###
def select_sinks(snks, date_start, date_end):
    '''This is a filler function, for now it is hard coded and very specific to
    the salt front location spreadsheet we have, but in the future it should look
    like the select_sources function from above'''
    
    print('Looking for sinks: ', snks)
    
    snks_list = list()
    snks_list_historical = list()
    
    date_start_pd = pd.to_datetime(date_start)
    date_end_pd = pd.to_datetime(date_end)

    #read in the salt front record
    sf_loc = pd.read_csv(os.path.join('03a_it_analysis', 'in', 'saltfront.csv'), parse_dates = True, index_col = 'datetime')
    sf_loc.index = sf_loc.index.date
    sf_loc.index = pd.to_datetime(sf_loc.index)
    #make a copy for historical
    sf_loc_historical = sf_loc[:date_end_pd.date()].copy()
    #save it to a list of _historical
    snks_list_historical.append(sf_loc_historical)
    snks_list_historical.append(sf_loc_historical)
    #trim sf_loc to the dates of interest
    sf_loc = sf_loc[date_start_pd.date():date_end_pd.date()]
    
    #we'll make snks_list a list of df here they are both 2019, but these could be different model runs 
    snks_list.append(sf_loc)
    snks_list.append(sf_loc)
    
    #add a suffix to one of the snks_list entries so we can tell the difference
    #snks_list[0] = snks_list[0].add_suffix('_Model_A')
    #snks_list_historical[0] = snks_list_historical[0].add_suffix('_Model_A')
    #noise = np.random.gamma(8, 2, len(sf_loc))
    #snks_list[0].iloc[:,0] = snks_list[0].iloc[:,0].add(noise)
    #snks_list[0].iloc[:,1] = snks_list[0].iloc[:,1].add(noise)
    return snks_list, snks_list_historical

###
def save_sources_sinks(srcs_list, snks_list, out_dir):
    #create out directory if it doesn't already exist
    os.makedirs(out_dir, exist_ok = True)
    #write snks_list to file 
    snks_file = open(out_dir+'snks_proc', "wb")
    pickle.dump(snks_list, snks_file)
    snks_file.close()
    #write srcs_list_lagged to file 
    srcs_file = open(out_dir+'srcs_proc_lagged', "wb")
    pickle.dump(srcs_list, srcs_file)
    srcs_file.close()
    print('sinks and sources saved to file')


###
def lag_sources(n_lags, srcs_list):
    '''Takes in the list of sources called srcs_list in which each list item is a 
    dataframe of site variables, and creates lagged time series for all variables
    according to the n_lag variable. Column headers are updted with the n_lag. n_lag refers
    to the number of time steps to lag, and it is agnostic of the time resolution of the data.
    length of data > n_lag >=0'''
    srcs_list_metrics = dict.fromkeys(srcs_list.keys())
    for key in srcs_list:
        site_list = srcs_list[key]
        #lag the source variables
        for s in range(len(site_list)):
            for col_name in list(site_list[s].columns):
                for lag in range(1, n_lags+1):
                    #create the lagged time series and name the columns
                    site_list[s][col_name+'_lag_'+str(lag)] = site_list[s][col_name].shift(lag)
            #sort the varaibles for ease of plotting
            site_list[s] = site_list[s].sort_index(axis=1)
        srcs_list_metrics[key] = site_list
    return srcs_list_metrics
###
class pre_proc_func:
    def __init__(self):
        pass

    def standardize(self, sr):
        standardized = list()
        for i in range(len(sr)):
            #standardize
            value_z = (sr[i] - np.nanmean(sr))/np.nanstd(sr, ddof = 1)
            standardized.append(value_z)
        return standardized

    def normalize(self, sr):
        normalized = list()
        for i in range(len(sr)):
            #normalize
            value_z = (sr[i]-np.nanmin(sr))/(np.nanmax(sr)-np.nanmin(sr))
            normalized.append(value_z)
        return normalized

    def remove_seasonal_signal(self, sr, sr_historical):
        #calculate doy for sr
        sr_doy = sr.index.strftime('%j')
        #convert sr_historical to df
        sr_historical_df = sr_historical.to_frame().copy()
        #calculate doy
        sr_historical_df['doy'] = list(sr_historical.index.strftime('%j'))
        #calculate the doy means
        doy_means = sr_historical_df.groupby('doy').mean()
        #convert the index (doy) to int64
        doy_means.index = doy_means.index.astype('int64')
        
        seasonal_removed = list()
        for i in range(len(sr)):
            doy = int(sr_doy[i])
            doy_mean = doy_means.loc[doy]
            value = sr.iloc[i]-doy_mean[0]
            seasonal_removed.append(value)
        return seasonal_removed

###
def apply_preprocessing_functions(var_list, var_list_historical, source_sink, out_dir, plot):
    '''Apply preprocessing functions to each variable. The preprocessing functions
    and the order that they are applied in are stored in the it_analysis_preprocess_config.yaml
    file. For each step in the process it saves a histogram of that data to the out_dir.
    The available preprocessing functions are of the class pre_proc_func and can be custom
    designed within the it_analysis_preprocess.py file. This function (apply_preprocessing_functions) has
    inputs and outputs that are structurally identical. Input is a list of dataframes of 'raw' data
    and output is a list of dataframes of processed data'''

    #import preprocessing steps from config
    preprocess_config = config['preprocess_steps']
    
    #get the functions of class pre_proc_func
    ppf = globals()['pre_proc_func']()
    
    #make an ouptut directory for the histograms
    os.makedirs(out_dir+'preprocess_plots', exist_ok=True)
    
    #make empty dictionary to store processed data, one entry for each metric
    processed_dict = dict.fromkeys(preprocess_config.keys())
    
    #for each metric
    for n_metric, metric in enumerate(preprocess_config.keys()):
        #print(n_metric, metric)
        
        #select the steps for the sources and sinks        
        if source_sink == 'sources':
            pre_process_steps = preprocess_config[metric]['sources']
        else:
            pre_process_steps = preprocess_config[metric]['sinks']
    
        #make new empty list of processed source data
        data_proc_list = []
        #for each entry in the list, likely each site
        for site_num, site_data in enumerate(var_list):
            #print(site_num, site_data)
            #create a new data frame with the same structure as the raw data
            var_proc_df = pd.DataFrame().reindex_like(var_list[site_num])
            #an empty list to be populated with source/sink variables from that site
            var_at_site = []
            #for each variable in the config file
            for i in list(pre_process_steps.keys()):
                #for each column name
                for j in var_proc_df.columns:
                    #check if the config file name is contained within the column name
                    if(i in j):
                        #if it is then put it in var_at_site
                        var_at_site.append(i)
            #for each preprocessing key
            for pp_key in var_at_site:
                print(pp_key)
                cols = list(var_proc_df.columns)
                #ucn is the unique column name
                #find the ucn that contains the pp_key, should only be one per var_list[site_num]
                ucn = [string for string in cols if pp_key in string][0]
                
                if plot:
                    #if the preprocess step is set to 'none' create a histogram of the raw data
                    fig, (ax1, ax2) = plt.subplots(2)
                    ax1.plot(var_list[site_num].index, var_list[site_num][ucn])
                    ax1.set_ylabel(ucn)
                    ax2.hist(var_list[site_num][ucn])
                    ax2.set_ylabel('Count')
                    plt.suptitle(ucn)
                    ax1.set_title('raw')
                    fig.savefig(out_dir+'preprocess_plots/' +ucn + '_raw.png', bbox_inches = 'tight')
                    #plt.show()
                    plt.close()

                if pre_process_steps[pp_key][0] == 'none':                    
                    #store the variable's data
                    raw_data = var_list[site_num][ucn].copy()
                    var_proc_df[ucn] = raw_data
                    print(ucn+'-- nothing to do here')
                else:
                    #if there are preprocessing steps to do
                    #store the data in temp data
                    temp_data = var_list[site_num][ucn].copy()
                    temp_data_historical = var_list_historical[site_num][ucn].copy()
                    
                    #for each preprocessing step for that variable
                    fname = os.path.join(out_dir, 'preprocess_plots', ucn)
                    for count,value in enumerate(pre_process_steps[pp_key]):
                        #apply the function
                        func = getattr(ppf,value)
                        
                        if value == 'remove_seasonal_signal':
                            #print('got the right function')
                            temp_data = func(temp_data, temp_data_historical)
                        else:
                            temp_data = func(temp_data)
                        
                        if plot:
                            #create histogram
                            fig, (ax1, ax2) = plt.subplots(2)
                            ax1.plot(var_list[site_num].index, temp_data)
                            ax1.set_ylabel(ucn)
                            ax2.hist(temp_data)
                            ax2.set_ylabel('Count')
                            #ax1.set_title(ucn + '_' + value + '_step ' + str(count+1)+ '/'+ str(len(pre_process_steps[pp_key])))
                            plt.suptitle(ucn)
                            if count==0:
                                pltsubt = value
                            else:                            
                                pltsubt = pltsubt+', '+ value
                            ax1.set_title(pltsubt)
                            fname = fname+'_'+ value
                            fig.savefig(fname+'.png', bbox_inches = 'tight')
                            #plt.show()
                            plt.close()
                        
                        #store the variable's data
                        var_proc_df[ucn] = temp_data
                        print(ucn+"-- apply: "+value)
            data_proc_list.append(var_proc_df)
        processed_dict[metric] = data_proc_list
    return(processed_dict)

###
def main():
    #select the sources
    srcs = config['srcs']
    #select the sinks
    snks = config['snks']
    #start date for analysis
    date_start = config['date_start']
    #end date for analysis
    date_end = config['date_end']
    #should preprocessing plots be saved
    plot = config['plot']
    
    #number of lag days to consider for sources
    n_lags = config['n_lags']
    #generate the sources data
    srcs_list, srcs_list_historical = select_sources(srcs, date_start, date_end)    
    #generate the sinks data
    snks_list, snks_list_historical = select_sinks(snks, date_start, date_end)
    #output file
    out_dir = config['out_dir'] 
    #process the sources
    srcs_proc = apply_preprocessing_functions(srcs_list, srcs_list_historical, 'sources', out_dir, plot)
    #process the sinks
    snks_proc = apply_preprocessing_functions(snks_list, snks_list_historical, 'sinks', out_dir, plot)

    #lag the sources
    srcs_list_lagged = lag_sources(n_lags, srcs_proc)
    out_dir = config['out_dir']
    save_sources_sinks(srcs_list_lagged, snks_proc, out_dir)
    
        
if __name__ == '__main__':
    main()