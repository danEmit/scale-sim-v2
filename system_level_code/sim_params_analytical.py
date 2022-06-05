import csv

make_plots = 1
run_system_specs = 1
make_plots = run_system_specs and make_plots

base_directory = "/Users/d/Desktop/onn_arch_system_design/"
results_file_path = base_directory + "results/" + "analytical_standalone" + "/"
NN_file_name = "Resnet50"
NN_file_folder = "topologies/ONN/"
NN_file_folder_mod = NN_file_folder.replace("/", "_") 
results_file_base_folder = results_file_path + NN_file_folder_mod + NN_file_name + "/"
sim_results_file_path_name = results_file_base_folder + NN_file_name + "__hardware_runspecs_info.csv"
chip_specs_file_path_name = results_file_base_folder + NN_file_name + "__chip_specs.csv"
detailed_results_folder = "layer_detail/"
detailed_results_folder_complete = results_file_base_folder + detailed_results_folder
plots_folder = "plots/"
plots_folder_complete = results_file_base_folder + plots_folder

SRAM_input_size_options  = [23868]
#SRAM_input_size_options  = [100000]
SRAM_input_size_options  = [23868 * 2 - 1]
SRAM_input_size_options = [802816]
#SRAM_input_size_options = [64000]
SRAM_filter_size_options = [300000]
SRAM_output_size_options = [300000]
#SRAM_output_size_options = [64000]


batch_size_options_overall = [1, 8, 16, 32, 64, 128]
array_size_options_overall = [[8, 8], [16, 16], [32, 32], [64, 64], [128, 128]]
accumulator_elements_options = [50000]
batch_size_options_index = [0]
array_size_options_index = [0]
batch_size_options = [batch_size_options_overall[x] for x in batch_size_options_index]
array_size_options = [array_size_options_overall[x] for x in array_size_options_index]

array_size_options = [[8, 16], [8, 32], [8, 64]]
array_size_options = [[16, 1], [32, 1], [64, 1], [128, 1], [256, 1]]
array_rows_options = [4, 8, 16, 32, 64, 128, 256]
array_cols_options = [4, 8, 16, 32, 64, 128, 256]


#array_rows_options = [12]
#array_cols_options = [12]

array_size_options = []
for array_rows in array_rows_options:
     for array_cols in array_cols_options:
          array_size_options.append([array_rows, array_cols])


symbol_rate_options = [1, 5, 10]
symbol_rate_options = [10]
all_layers = []

if (0):
     if (1):
          input_height  = [10, 5]
          input_width   = [10, 5] 
          filter_height = [3, 4]
          filter_width  = [3, 4]
          channels = [2, 1]
          num_filter = [10, 3]
          strides = [1, 1]

     num_layers = len(input_height) 
     all_layers = []
     for layer in range(num_layers):
          layer_dict = {"Input Height" : input_height[layer], "Input Width" : input_width[layer], "Filter Height" : filter_height[layer], "Filter Width": filter_width[layer], \
               "Channels" : channels[layer], "Num Filter" : num_filter[layer], "Strides" : strides[layer]}
          all_layers.append(layer_dict)
          
     for ind in range(len(channels) - 1):
          if (num_filter[ind] != channels[ind + 1]):
               print("\nNote that this is not a valid NN, the number of filters in layer ", str(ind), " is different from the number of channels in layer ", str(ind + 1), sep = "")

else:
     input_rows = [] 
     input_cols  = []
     filter_rows = [] 
     filter_cols = []
     channels = []
     num_filter = []
     strides = []

     NN_directory = base_directory + NN_file_folder + NN_file_name + ".csv"

     with open(NN_directory, newline='') as csvfile:
          spamreader = csv.reader(csvfile, delimiter=',')
          firstRow = 1
          for row in spamreader:
               if firstRow:
                    firstRow = 0
                    continue
               try:
                    layer_dict = {"Input Height" : int(row[1]), "Input Width" : int(row[2]), "Filter Height" : int(row[3]), "Filter Width": int(row[4]), \
                    "Channels" : int(row[5]), "Num Filter" : int(row[6]), "Strides" : int(row[7])}
                    all_layers.append(layer_dict)
               except:
                    print("can't convert all the data in NN file to ints")








