def length_of_longest_substring(s):
    # Initialize variables
    char_index_map = {}
    start = 0
    max_length = 0

    # Iterate over the string with index
    for end in range(len(s)):
        # If the character is already in the map and its index is within the current window
        if s[end] in char_index_map and char_index_map[s[end]] >= start:
            # Move the start to the right of the last occurrence of the character
            start = char_index_map[s[end]] + 1
        else:
            # Update the maximum length if the current window is larger
            max_length = max(max_length, end - start + 1)

        # Update the character's index in the map
        char_index_map[s[end]] = end

    return max_length

# Test the function with a sample input
sample_input = "abcabcbb"
print(length_of_longest_substring(sample_input))  # Output: 3