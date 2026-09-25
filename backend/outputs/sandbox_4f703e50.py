def merge_intervals(intervals):
    # Sort intervals by their start value
    intervals.sort(key=lambda x: x[0])
    
    # Initialize the result list with the first interval
    result = [intervals[0]]
    
    # Iterate through the sorted intervals
    for interval in intervals[1:]:
        # Get the last interval in the result list
        last = result[-1]
        
        # If the current interval overlaps with the last interval in the result
        if interval[0] <= last[1]:
            # Merge the intervals
            last[1] = max(last[1], interval[1])
        else:
            # Add the current interval to the result list
            result.append(interval)
    
    return result

# Test cases
print(merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]]))  # Output: [[1, 6], [8, 10], [15, 18]]
print(merge_intervals([[1, 4], [4, 5]]))  # Output: [[1, 5]]
print(merge_intervals([[5, 7], [1, 3], [2, 6], [8, 10]]))  # Output: [[1, 7], [8, 10]]
print(merge_intervals([]))  # Output: []