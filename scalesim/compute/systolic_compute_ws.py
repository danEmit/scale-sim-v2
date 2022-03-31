import math
import numpy as np
from tqdm import tqdm
from scalesim.scale_config import scale_config as cfg

import scalesim.global_vars as global_vars

class systolic_compute_ws:
    def __init__(self):
        # Params set by user
        self.config = cfg()

        self.ifmap_op_mat = np.zeros((1, 1))
        self.ofmap_op_mat = np.zeros((1, 1))
        self.filter_op_mat = np.zeros((1, 1))

        # Derived parameters
        self.Sr = 0
        self.Sc = 0
        self.T = 0

        self.arr_row = 0
        self.arr_col = 0

        self.row_fold = 1
        self.col_fold = 1

        # Generated matrices
        self.ifmap_op_mat_trans = np.zeros((1,1))
        self.ifmap_prefetch_matrix = np.zeros((1,1))
        self.filter_prefetch_matrix = np.zeros((1,1))

        self.ifmap_demand_matrix = np.zeros((1,1))
        self.ofmap_demand_matrix = np.zeros((1,1))
        self.filter_demand_matrix = np.zeros((1,1))

        self.ifmap_demand_matrix_NON_SKEW = np.zeros((1,1))

        # Generated metrics
        self.ifmap_reads = 0
        self.filter_reads = 0
        self.ofmap_writes = 0

        self.mapping_efficiency_per_fold = []
        self.compute_utility_per_fold = []

        # Flags
        self.params_set_flag = False
        self.prefetch_mat_ready_flag = False
        self.demand_mat_ready_flag = False

    #
    def set_params(self,
                   config_obj=cfg(),
                   ifmap_op_mat = np.zeros((1,1)),
                   ofmap_op_mat = np.zeros((1,1)),
                   filter_op_mat = np.zeros((1,1))
                ):

        self.config = config_obj
        self.ifmap_op_mat = ifmap_op_mat
        self.filter_op_mat = filter_op_mat
        self.ofmap_op_mat = ofmap_op_mat

        ifmap_col = self.ifmap_op_mat.shape[1]
        filter_row= self.filter_op_mat.shape[0]

        assert ifmap_col == filter_row, "Dimension mismatch between operands"

        self.Sr = self.ifmap_op_mat.shape[1]
        self.Sc = self.filter_op_mat.shape[1]
        self.T = self.ifmap_op_mat.shape[0]

        self.arr_row, self.arr_col = self.config.get_array_dims()

        self.row_fold = math.ceil(self.Sr / self.arr_row)
        self.col_fold = math.ceil(self.Sc / self.arr_col)

        global_vars.num_program.append(self.row_fold * self.col_fold)

        self.params_set_flag = True

    #
    def create_prefetch_matrices(self):
        assert self.params_set_flag, 'Parameters are not set'

        self.create_ifmap_prefetch_mat()
        self.create_filter_prefetch_mat()

        self.prefetch_mat_ready_flag = True

    #
    def create_ifmap_prefetch_mat(self):
        assert self.params_set_flag, 'Parameters are not set'

        for fr in range(self.row_fold):
            start_col_idx = fr * self.arr_row
            end_col_idx = min(start_col_idx + self.arr_row, self.Sr)

            delta = self.arr_row - (end_col_idx - start_col_idx)

            this_fold_prefetch = self.ifmap_op_mat[:,start_col_idx: end_col_idx]

            #If there is under utilization, fill them with null requests
            if delta > 0:
                null_req_mat = np.ones((self.T, delta)) * -1
                this_fold_prefetch = np.concatenate((this_fold_prefetch, null_req_mat), axis=1)

            if fr == 0:
                self.ifmap_prefetch_matrix = this_fold_prefetch
            else:
                self.ifmap_prefetch_matrix = np.concatenate((self.ifmap_prefetch_matrix, this_fold_prefetch), axis=0)

        # Fixing ISSUE #15, #16
        # Roll out the matrices along the diagonal to account for temporal locality when there is a skew in demand

        M, N = self.ifmap_prefetch_matrix.shape
        num_elems = M * N
        num_diags = M + N
        prefetches = np.zeros((1, num_elems))
        idx = 0

        pbar = tqdm(total=M * N, disable=True)
        # print('DEBUG: Total = ' + str(num_elems) + ' Diags = ' + str(num_diags))

        for diag_id in range(num_diags):
            max_row_id = min(diag_id, M - 1)
            min_row_id = max(0, diag_id - N + 1)
            valid_rows = max_row_id - min_row_id + 1

            for offset in range(valid_rows):
                row_id = max_row_id - offset
                col_id = diag_id - row_id

                elem = self.ifmap_prefetch_matrix[row_id][col_id]
                prefetches[0, idx] = elem
                idx += 1
                pbar.update(1)

        pbar.close()
        self.ifmap_prefetch_matrix = prefetches

    #
    def create_filter_prefetch_mat(self):
        assert self.params_set_flag, 'Parameters are not set'

        for fc in range(self.col_fold):
            col_start_id = fc * self.arr_col
            col_end_id = min(col_start_id + self.arr_col, self.Sc)

            delta = self.arr_col - (col_end_id - col_start_id)

            this_fold_prefetch = self.filter_op_mat[:,col_start_id:col_end_id]

            if delta > 0:
                null_req_mat = np.ones((self.Sr, delta)) * -1
                this_fold_prefetch = np.concatenate((this_fold_prefetch, null_req_mat), axis=1)

            if fc == 0:
                self.filter_prefetch_matrix = this_fold_prefetch
            else:
                self.filter_prefetch_matrix = np.concatenate((self.filter_prefetch_matrix, this_fold_prefetch), axis=0)

        # Note: ISSUE #15: no skewing happens in the Filter for WS so this issue does not apply.

    #
    def create_demand_matrices(self):
        assert self.params_set_flag, 'Parameters are not set'

        self.create_ifmap_demand_mat()
        self.create_filter_demand_mat()
        self.create_ofmap_demand_mat()

        assert self.ifmap_demand_matrix.shape[0] == self.filter_demand_matrix.shape[0], 'IFMAP and Filter demands out of sync'
        assert self.ofmap_demand_matrix.shape[0] == self.filter_demand_matrix.shape[0], 'OFMAP and Filter demands out of sync'
        assert self.ifmap_demand_matrix.shape[1] == self.arr_row, 'IFMAP demands exceed the rows'
        assert self.filter_demand_matrix.shape[1] == self.arr_col,'Filter demands exceed the cols'
        assert self.ofmap_demand_matrix.shape[1] == self.arr_col, 'OFMAP demands exceed the cols'

        self.demand_mat_ready_flag = True

    #
    def create_ifmap_demand_mat(self):
        assert self.params_set_flag, 'Parameters are not set'

        inter_fold_gap_prefix = self.arr_row
        inter_fold_gap_prefix_mat = np.ones((inter_fold_gap_prefix, self.arr_row)) * -1

        # my change is necesssary to counteract their update, their's causes issues
        #inter_fold_gap_suffix = self.arr_row + self.arr_col - 2
        inter_fold_gap_suffix = self.arr_col - 1

        #The last input needs self.arr_row - 1 cycles to reach the last column of PE array and then self.arr_col - 1 cycles to reduce along the last column.

        inter_fold_gap_suffix_mat = np.ones((inter_fold_gap_suffix, self.arr_row)) * -1

        for fc in range(self.col_fold):
            for fr in range(self.row_fold):
                col_start_id = fr * self.arr_row
                col_end_idx = min(col_start_id + self.arr_row, self.Sr)
                delta = self.arr_row - (col_end_idx - col_start_id)

                # Indexing the cols with row start and row end idx are correct
                # See the comment on ifmap_prefetch generation
                this_fold_demand = self.ifmap_op_mat[:,col_start_id: col_end_idx]
                self.ifmap_reads += this_fold_demand.shape[0] * this_fold_demand.shape[1]

                # Take into account under utilization
                if delta > 0:
                    null_req_mat = np.ones((self.T, delta)) * -1
                    this_fold_demand = np.concatenate((this_fold_demand, null_req_mat), axis=1)

                # Account for the cycles for weights to load
                this_fold_demand = np.concatenate((inter_fold_gap_prefix_mat, this_fold_demand), axis=0)

                # Account for the cycles for final output to drain out
                this_fold_demand = np.concatenate((this_fold_demand, inter_fold_gap_suffix_mat), axis=0)
                this_fold_demand_non_skew = this_fold_demand
                #self.ifmap_demand_matrix_NON_SKEW = this_fold_demand

                # Add skew to the IFMAP demand matrix to reflect systolic pipeline fill
                this_fold_demand = skew_matrix(this_fold_demand)

                if fr == 0 and fc == 0:
                    self.ifmap_demand_matrix = this_fold_demand
                    self.ifmap_demand_matrix_NON_SKEW = this_fold_demand_non_skew
                else:
                    self.ifmap_demand_matrix = np.concatenate((self.ifmap_demand_matrix, this_fold_demand), axis=0)
                    self.ifmap_demand_matrix_NON_SKEW = np.concatenate((self.ifmap_demand_matrix_NON_SKEW, this_fold_demand_non_skew), axis = 0)
    # END of IFMAP demand generation

    #
    def create_filter_demand_mat(self):
        assert self.params_set_flag, 'Parameters are not set'

        inter_fold_gap_suffix = self.arr_row + self.arr_col + self.T - 2
        inter_fold_gap_suffix_mat = np.ones((inter_fold_gap_suffix, self.arr_col)) * -1

        for fc in range(self.col_fold):
            for fr in range(self.row_fold):
                row_start_id = fr * self.arr_row
                row_end_idx = min(row_start_id + self.arr_row, self.Sr)
                row_delta = self.arr_row - (row_end_idx - row_start_id)

                col_start_id = fc * self.arr_col
                col_end_idx = min(col_start_id + self.arr_col, self.Sc)
                col_delta = self.arr_col - (col_end_idx - col_start_id)

                this_fold_demand = self.filter_op_mat[row_start_id:row_end_idx, col_start_id: col_end_idx]
                self.filter_reads += this_fold_demand.shape[0] * this_fold_demand.shape[1]

                # Take into account under utilization
                if col_delta > 0:
                    null_req_mat = np.ones((this_fold_demand.shape[0], col_delta)) * -1
                    this_fold_demand = np.concatenate((this_fold_demand, null_req_mat), axis=1)

                if row_delta > 0:
                    null_req_mat = np.ones((row_delta, self.arr_col)) * -1
                    this_fold_demand = np.concatenate((this_fold_demand, null_req_mat), axis=0)

                # The filters are needed to be filled in reverse order to ensure that
                # top element is pushed in last to maintain alignment with the input elements
                this_fold_demand = np.flip(this_fold_demand, 0)

                # Time for inputs to stream and the partial sums to drain out
                this_fold_demand = np.concatenate((this_fold_demand, inter_fold_gap_suffix_mat), axis=0)

                # Calculate the mapping efficiency
                row_used = min(self.arr_row, row_end_idx - row_start_id)
                col_used = min(self.arr_col, col_end_idx - col_start_id)
                mac_used = row_used * col_used
                mapping_eff_this_fold = mac_used / (self.arr_row * self.arr_col)

                cycles_this_fold = this_fold_demand.shape[0] + this_fold_demand.shape[1] - 1
                compute_cycles_this_fold = mac_used * self.T
                compute_util_this_fold = compute_cycles_this_fold / (self.arr_row * self.arr_col * cycles_this_fold)

                self.mapping_efficiency_per_fold.append(mapping_eff_this_fold)
                self.compute_utility_per_fold.append(compute_util_this_fold)

                if fr == 0 and fc == 0:
                    self.filter_demand_matrix = this_fold_demand
                else:
                    self.filter_demand_matrix = np.concatenate((self.filter_demand_matrix, this_fold_demand), axis=0)

        # No skew needed in filters for weight stationary

    #
    def create_ofmap_demand_mat(self):
        assert self.params_set_flag, 'Parameters are not set'

        inter_fold_gap_prefix = 2 * self.arr_row - 1
        inter_fold_gap_prefix_mat = np.ones((inter_fold_gap_prefix, self.arr_col)) * -1

        for fc in range(self.col_fold):
            for fr in range(self.row_fold):
                col_start_id = fc * self.arr_col
                col_end_idx = min(col_start_id + self.arr_col, self.Sc)
                col_delta = self.arr_col - (col_end_idx - col_start_id)

                this_fold_demand = self.ofmap_op_mat[:, col_start_id: col_end_idx]
                self.ofmap_writes += this_fold_demand.shape[0] * this_fold_demand.shape[1]

                # Adding null requests when there is under utilization ie. no mapping along a few rows or cols
                if col_delta > 0:
                    null_req_mat = np.ones((this_fold_demand.shape[0], col_delta)) * -1
                    this_fold_demand = np.concatenate((this_fold_demand, null_req_mat), axis=1)

                # Now add the prefix matrix
                # These are the null demands to account for when the operands are streamed in
                # and the OFMAPS are not ready
                this_fold_demand = np.concatenate((inter_fold_gap_prefix_mat, this_fold_demand), axis=0)

                # Add skew to the OFMAP demand matrix to reflect systolic pipeline fill
                this_fold_demand = skew_matrix(this_fold_demand)

                if fr == 0 and fc == 0:
                    self.ofmap_demand_matrix = this_fold_demand
                else:
                    self.ofmap_demand_matrix = np.concatenate((self.ofmap_demand_matrix, this_fold_demand), axis=0)
    # END of OFMAP demand generation

    #
    def get_ifmap_prefetch_mat(self):
        if not self.prefetch_mat_ready_flag:
            self.create_prefetch_matrices()

        return self.ifmap_prefetch_matrix

    #
    def get_filter_prefetch_mat(self):
        if not self.prefetch_mat_ready_flag:
            self.create_prefetch_matrices()

        return self.filter_prefetch_matrix

    #
    def get_prefetch_matrices(self):
        if not self.prefetch_mat_ready_flag:
            self.create_prefetch_matrices()

        return self.ifmap_prefetch_matrix, self.filter_prefetch_matrix

    #
    def get_ifmap_demand_mat(self):
        if not self.demand_mat_ready_flag:
            self.create_demand_matrices()

        return self.ifmap_demand_matrix

    #
    def get_filter_demand_mat(self):
        if not self.demand_mat_ready_flag:
            self.create_demand_matrices()

        return self.filter_demand_matrix

    #
    def get_ofmap_demand_mat(self):
        if not self.demand_mat_ready_flag:
            self.create_demand_matrices()

        return self.ofmap_demand_matrix

    #
    def get_demand_matrices(self):
        if not self.demand_mat_ready_flag:
            self.create_demand_matrices()

        return self.ifmap_demand_matrix, self.filter_demand_matrix, self.ofmap_demand_matrix, self.ifmap_demand_matrix_NON_SKEW

    #
    def get_avg_mapping_efficiency(self):
        assert self.demand_mat_ready_flag, 'Computes not ready yet'

        agg = sum(self.mapping_efficiency_per_fold)
        num = len(self.mapping_efficiency_per_fold)

        avg_mapping_eff = agg / num

        return avg_mapping_eff

    #
    def get_avg_compute_utilization(self):
        assert self.demand_mat_ready_flag, 'Computes not ready yet'

        agg = sum(self.compute_utility_per_fold)
        num = len(self.compute_utility_per_fold)

        avg_compute_util = agg / num

        return avg_compute_util

    #
    def get_ifmap_requests(self):
        assert self.demand_mat_ready_flag, 'Computes not ready yet'
        return self.ifmap_reads

    #
    def get_filter_requests(self):
        assert self.demand_mat_ready_flag, 'Computes not ready yet'
        return self.filter_reads

    #
    def get_ofmap_requests(self):
        assert self.demand_mat_ready_flag, 'Computes not ready yet'
        return self.ofmap_writes


#
def skew_matrix(input_matrix_np):
    rows = input_matrix_np.shape[0]
    cols = input_matrix_np.shape[1]

    out_matrix_np = np.zeros((1,1))
    for c in range(cols):
        if c == 0:
            down_padding = -1 * np.ones((cols-1, 1))
            mat_col = input_matrix_np[:,c].reshape((rows,1))
            out_matrix_np = np.concatenate((mat_col, down_padding), axis=0)

        else:
            if c == cols -1:
                up_padding = -1 * np.ones((cols-1, 1))
                mat_col = input_matrix_np[:, c].reshape((rows, 1))

                this_col = np.concatenate((up_padding, mat_col), axis=0)
                out_matrix_np = np.concatenate((out_matrix_np, this_col), axis=1)

            else:
                up_padding = -1 * np.ones((c, 1))
                mat_col = input_matrix_np[:, c].reshape((rows, 1))
                down_padding = -1 * np.ones((cols - c-1, 1))

                this_col = np.concatenate((up_padding, mat_col, down_padding), axis=0)
                out_matrix_np = np.concatenate((out_matrix_np, this_col), axis=1)

    return out_matrix_np
