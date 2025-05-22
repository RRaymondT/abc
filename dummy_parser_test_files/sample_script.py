
import os

def source_function_for_flow():
    return "raw_data"

def process_data_for_flow(input_data, other_param=None):
    processed = input_data.upper()
    if other_param:
        print(f"Other param: {other_param}")
    return processed

def another_source():
    return "another_piece_of_data"

def final_sink(data1, data2):
    print(f"Sink received: {data1} and {data2}")

def data_flow_test():
    # Direct flow
    data_from_source = source_function_for_flow() 
    # 'data_from_source' (from 'source_function_for_flow') flows into 'process_data_for_flow' as 'input_data'
    result1 = process_data_for_flow(input_data=data_from_source, other_param=123) 
    
    # Second variable from a different source
    other_data = another_source()
    
    # 'result1' (from 'process_data_for_flow') flows into 'final_sink' as 'data1'
    # 'other_data' (from 'another_source') flows into 'final_sink' as 'data2'
    final_sink(result1, data2=other_data)

class MyClassWithFlow:
    def method_flow(self):
        m_data = self.source_method()
        self.sink_method(m_data)

    def source_method(self):
        return "method_data"
    
    def sink_method(self, data_param):
        print(data_param)

