def subarray_sum(nums, k):
    # Dictionary to store the cumulative sum and its frequency
    sum_count = {0: 1}
    current_sum = 0
    count = 0
    
    for num in nums:
        # Update the current sum
        current_sum += num
        
        # Calculate the difference between the current sum and k
        difference = current_sum - k
        
        # If the difference is in the dictionary, it means there is a subarray summing to k
        if difference in sum_count:
            count += sum_count[difference]
        
        # Update the dictionary with the current sum
        if current_sum in sum_count:
            sum_count[current_sum] += 1
        else:
            sum_count[current_sum] = 1
    
    return count

# Example usage
nums = [1, 1, 1, 1, 1]
k = 2
print(subarray_sum(nums, k))  # Output: 4