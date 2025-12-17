<h2>
Upload BGP and Static routing details in Prisma SDWAN  
</h2>

<br>
<br>
Before Getting Started this script uses the prisma_sase sdk https://github.com/PaloAltoNetworks/prisma-sase-sdk-python - to install it run "pip3 install prisma_sase" 
<br>
Update the routing_data.csv with your data, some are static payloads you can change in the python script itself! it checks to see if the object exissts if so updates online, if not then creates it.
<br>
set your creds in the prismasase_settings.py.example and change the extension by removing the .example
<br>
<br>
<strong>To run: </strong> python3 ./route_csv_programmer.py with the CSV file in the same directory.
<br>
<br>
<br>
Output looks like this... 
<br>
<br>
--- Logging in to Prisma SASE ---

--- Building ID Lookup Maps ---
  > Loaded 13 sites.
  > Loaded 14 elements.
  > Loaded 8 VRFs.

--- Reading routing_data.csv ---

--- Processing 2 Rows ---

Row 1: Site='SHELLSITE', Element='shell1'
    [*] Updating BGP Peer 'PEER1'...
    [OK] BGP Peer 'PEER1' configured successfully.
    [*] Updating Static Route 'VRFA-TO-PRISMA' (0.0.0.0/0 -> 172.21.1.1)...
    [OK] Static Route 'VRFA-TO-PRISMA' configured successfully.

Row 2: Site='SHELLSITE', Element='shell1'
    [+] Creating BGP Peer 'PEER2'...
    [OK] BGP Peer 'PEER2' configured successfully.
    [*] Updating Static Route 'VRFB-TO-PRISMA' (0.0.0.0/0 -> 172.21.2.1)...
    [OK] Static Route 'VRFB-TO-PRISMA' configured successfully.

<br>
<br>
<strong>Use at own risk :)</strong>
