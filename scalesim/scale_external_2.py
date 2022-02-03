#import argparse
import sys
import numpy as np
import time
import os
import pandas as pd

import scalesim.global_vars as global_vars


from scalesim.scale_sim import scalesim
SS_results_file_global = ""

SS_outputs_names = ["SRAM Input Reads", "SRAM Filter Reads", "SRAM Output Writes", "DRAM Input Reads", "DRAM Filter Reads", "DRAM Output Writes", \
          "Total Weights Programming Cycles", "Total Vector Segments Processed"]
SS_outputs_data = [0] * len(SS_outputs_names)
SS_outputs = pd.DataFrame(SS_outputs_data, index = SS_outputs_names, columns = [""])

debugPrint = 0

def analyze_memory_writes():
    # here are some magic numbers. they are important!
    SRAM_IFMAP_READS  = 2
    SRAM_FILTER_READS = 5
    SRAM_OFMAP_WRITES = 8
    DRAM_IFMAP_READS  = 11
    DRAM_FILTER_READS = 14
    DRAM_OFMAP_WRITES = 17

    sram_reads  = 0
    sram_writes = 0
    dram_reads  = 0
    dram_writes = 0
    #print("\nWill now analyze memory accesses")

    sram_ifmap_reads  = 0
    sram_filter_reads = 0
    sram_ofmap_writes = 0

    dram_ifmap_reads  = 0
    dram_filter_reads = 0
    dram_ofmap_writes = 0

    for row in global_vars.memoryAccess:
        sram_reads  += row[SRAM_IFMAP_READS] + row[SRAM_FILTER_READS]
        sram_writes += row[SRAM_OFMAP_WRITES]
        dram_reads  += row[DRAM_IFMAP_READS] + row[DRAM_FILTER_READS]
        dram_writes += row[DRAM_OFMAP_WRITES]

        sram_ifmap_reads  += row[SRAM_IFMAP_READS]
        sram_filter_reads += row[SRAM_FILTER_READS]
        sram_ofmap_writes += row[SRAM_OFMAP_WRITES]

        dram_ifmap_reads  += row[DRAM_IFMAP_READS]
        dram_filter_reads += row[DRAM_FILTER_READS]
        dram_ofmap_writes += row[DRAM_OFMAP_WRITES]

    print()
    if (debugPrint):
        print("SRAM Input Reads:   ", sram_ifmap_reads)
        print("SRAM Filter Reads:  ", sram_filter_reads)
        print("SRAM Output Writes: ", sram_ofmap_writes)

        print("DRAM Input Reads:   ", dram_ifmap_reads)
        print("DRAM Filter Reads:  ", dram_filter_reads)
        print("DRAM Output Writes: ", dram_ofmap_writes)
        print()

    SS_outputs.at["SRAM Input Reads":"DRAM Output Writes", ""] = [sram_ifmap_reads, sram_filter_reads, sram_ofmap_writes, \
        dram_ifmap_reads, dram_filter_reads, dram_ofmap_writes]


def analyze_SRAM_trace(SRAM_demand_mat):
    numLayers = len(SRAM_demand_mat)
    SRAM_cycles = [0] * numLayers
    for layer in range(numLayers):
        row_idx = 0
        SRAM_cycles[layer] = []
        SRAM_demand_mat_singleLayer = SRAM_demand_mat[layer]
        while (row_idx < SRAM_demand_mat_singleLayer.shape[0]):
            row = SRAM_demand_mat_singleLayer[row_idx, :] 
            program_row_count = 0
            program_col_count = 0 #redundant?
             
            while(sum(row == -1) != row.shape[0]):
                if (program_row_count == 0):
                    program_col_count = sum(row != -1)
                program_row_count += 1
                row_idx += 1
                row = SRAM_demand_mat_singleLayer[row_idx, :]  

            if program_row_count != 0: 
                statsRow = [program_row_count, program_col_count, program_col_count * program_row_count]
                SRAM_cycles[layer].append(statsRow)
            
            else:
                row_idx += 1
                
        SRAM_cycles[layer] = np.array(SRAM_cycles[layer])

    return SRAM_cycles


def analyze_SRAM_usage():
    input_demand_mat = global_vars.ifmap_demand_mat
    filter_demand_mat = global_vars.filter_demand_mat
    output_demand_mat = global_vars.ofmap_demand_mat
    input_demand_mat_non_skew = global_vars.ifmap_demand_mat_non_skew

    filter_SRAM_cycles = analyze_SRAM_trace(filter_demand_mat)
    num_weight_programming_cycles_total = 0
    num_weight_programming_ind_total = 0
    if (debugPrint):
        print("\nWeights programming stats by NN layer:")
    for layerNum in range(len(filter_SRAM_cycles)):
        num_weight_programming_cycles_layer = filter_SRAM_cycles[layerNum].shape[0]
        num_weight_programming_cycles_total += num_weight_programming_cycles_layer
        
        num_weight_programming_ind_layer = sum(filter_SRAM_cycles[layerNum][:, 2])
        num_weight_programming_ind_total += num_weight_programming_ind_layer
        
        if (debugPrint):
            print("layer:",layerNum)
            print("# programming cycles:",num_weight_programming_cycles_layer, "------- # ind weights programmed:",num_weight_programming_ind_layer)
        #print("Details on weights programming cycles - rows, columns, total weights:")
        #print(filter_SRAM_cycles[layerNum])
    
    if (debugPrint):
        print("\nTOTAL WEIGHTS PROGRAMMING CYCLES:", num_weight_programming_cycles_total)
        print("TOTAL INDIVIDUAL WEIGHTS PRORGRAMMED:", num_weight_programming_ind_total)
    #print()
    
    
    input_SRAM_cycles = analyze_SRAM_trace(input_demand_mat_non_skew)
    num_compute_cycles_total = 0
    num_input_compute_vector_segments_total = 0
    if (debugPrint):
        print("\nInput computation vectors stats by NN layer:")
    for layerNum in range(len(input_SRAM_cycles)):
        num_compute_cycles_layer = input_SRAM_cycles[layerNum].shape[0]
        num_compute_cycles_total += num_compute_cycles_layer
        
        num_input_compute_vector_segments_layer = sum(input_SRAM_cycles[layerNum][:, 0])
        num_input_compute_vector_segments_total += num_input_compute_vector_segments_layer
        
        if (debugPrint):
            print("layer:", layerNum)
            print("# compute cycles:", num_compute_cycles_layer, "------- # ind input vector SEGMENTS processed:", num_input_compute_vector_segments_layer)
    
    if (debugPrint):
        print("\nTOTAL COMPUTE CYCLES:", num_compute_cycles_total)
        print("TOTAL VECTOR SEGMENTS PROCESSED IN ARRAY:", num_input_compute_vector_segments_total)
    #print()

    SS_outputs.at["Total Weights Programming Cycles":"Total Vector Segments Processed", ""] = [num_compute_cycles_total, num_input_compute_vector_segments_total]

def post_process():
    #print("\n**** Will now do post-processing ****")
    analyze_memory_writes()
    analyze_SRAM_usage()


def run_scale_sim(config_file_path, NN_file_path, SS_folder_outputs):
    global_vars.initialize()

    gemm_input = False

    #print("inputted topology file")
    #print(NN_file_path)
    s = scalesim(save_disk_space=True, verbose=False,
                 config=config_file_path,
                 topology=NN_file_path,
                 input_type_gemm=gemm_input
                 )
    startExecutionTime = time.time()
    logpath = SS_folder_outputs
    #logpath = "../test_runs"
    print(logpath)
    s.run_scale(top_path=logpath)
    endExecutionTime = time.time()
    #print("\nTOTAL EXECUTION TIME:", round((endExecutionTime - startExecutionTime), 3))
    #print()

    post_process()
    #analyze_memory_writes()
    #analyze_SRAM_usage()
    endPostProcessTime = time.time()
    #print("\nTOTAL POST PROCESS TIME:", round((endPostProcessTime - endExecutionTime), 3))

    return(SS_outputs)







