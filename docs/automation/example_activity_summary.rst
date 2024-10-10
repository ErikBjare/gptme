.. rubric:: Example: Daily Activity Summary

Here's an example of how to use gptme to generate a daily summary based on ActivityWatch data using a shell script:

.. code-block:: bash

   #!/bin/bash

   # Function to get yesterday's date in YYYY-MM-DD format
   get_yesterday() {
       date -d "yesterday" +%Y-%m-%d
   }

   # Function to get ActivityWatch report
   get_aw_report() {
       local date=$1
       aw-client report $(hostname) --start $date --stop $(date -d "$date + 1 day" +%Y-%m-%d)
   }

   # Generate daily summary
   generate_daily_summary() {
       local yesterday=$(get_yesterday)
       local aw_report=$(get_aw_report $yesterday)

       # Create a temporary file
       local summary_file=$(mktemp)

       # Generate summary using gptme
       gptme --non-interactive "Based on the following ActivityWatch report for $yesterday, provide a concise summary of yesterday's activities.
       Include insights on productivity, time spent on different categories, and any notable patterns.
       Suggest areas for improvement if applicable.

       ActivityWatch Report:
       $aw_report

       Please format the summary in a clear, easy-to-read structure.
       Save the summary to this file: $summary_file"

       # Return the path to the summary file
       echo "$summary_file"
   }

   # Run the summary generation and get the file path
   summary_file=$(generate_daily_summary)

   # Output the file path (you can use this in other scripts or log it)
   echo "Daily summary saved to: $summary_file"

To automate this process to run every day at 8 AM, you could set up a cron job. Here's an example cron entry:

.. code-block:: bash

   0 8 * * * /path/to/daily_summary_script.sh

This automation will provide you with daily insights into your computer usage and productivity patterns from the previous day, leveraging the power of gptme to analyze and summarize the data collected by ActivityWatch.
