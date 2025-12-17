#!/usr/bin/env python3
"""
Script to Automate BGP & Static Routing
Author: Aaron Ratcliffe @ PANW
Version 1.0.1-b
Use at own risk :)
"""

import prisma_sase
from prisma_sase import jd
from prisma_sase import API
import json
import csv
import sys
import os
try:
    import prismasase_settings
except ImportError:
    prismasase_settings = None

# ----------------------------------------------------------------------------
# CSV Configuration
# ----------------------------------------------------------------------------
CSV_FILE = "routing_data.csv"

# ----------------------------------------------------------------------------
# Standard Payload Definitions
# ----------------------------------------------------------------------------
PREFIX_LIST_ENTRIES = [
    {
        "action": "deny", 
        "prefix": "0.0.0.0/0", 
        "le": 32, 
        "ge": 0
    }
]

def get_route_map_entries(prefix_list_id):
    return [
        {
            "order": 10,
            "permit": True,
            "match": {"ip_prefix_list_id": prefix_list_id},
            "set": {"local_preference": 100}
        }
    ]

# ----------------------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------------------
def ensure_prefix_list(sdk, site_id, element_id, name):
    resp = sdk.get.routing_prefixlists(site_id=site_id, element_id=element_id)
    if not resp.cgx_status:
        print(f"    [!] Error getting prefix lists: {resp.cgx_content}")
        return None
    
    existing = {item['name']: item for item in resp.cgx_content.get('items', [])}
    if name in existing:
        return existing[name]['id']
    
    print(f"    [+] Creating Prefix List '{name}'...")
    payload = {
        "name": name, 
        "description": "Auto-created by script", 
        "entries": PREFIX_LIST_ENTRIES
    }
    resp = sdk.post.routing_prefixlists(site_id=site_id, element_id=element_id, data=payload)
    if not resp.cgx_status:
        print(f"    [!] Error creating prefix list: {resp.cgx_content}")
        return None
    return resp.cgx_content['id']

def ensure_route_map(sdk, site_id, element_id, name, prefix_list_id):
    resp = sdk.get.routing_routemaps(site_id=site_id, element_id=element_id)
    if not resp.cgx_status:
        print(f"    [!] Error getting route maps: {resp.cgx_content}")
        return None
    
    existing = {item['name']: item for item in resp.cgx_content.get('items', [])}
    if name in existing:
        return existing[name]['id']
    
    print(f"    [+] Creating Route Map '{name}'...")
    payload = {
        "name": name,
        "description": "Auto-created by script",
        "routes": get_route_map_entries(prefix_list_id)
    }
    resp = sdk.post.routing_routemaps(site_id=site_id, element_id=element_id, data=payload)
    if not resp.cgx_status:
        print(f"    [!] Error creating route map: {resp.cgx_content}")
        return None
    return resp.cgx_content['id']

def create_bgp_peer(sdk, site_id, element_id, peer_data, rm_out_id, vrf_id):
    name = peer_data['peer_name']
    resp = sdk.get.bgppeers(site_id=site_id, element_id=element_id)
    if not resp.cgx_status:
        print(f"    [!] Error getting BGP peers: {resp.cgx_content}")
        return False

    existing_peers = {item['name']: item for item in resp.cgx_content.get('items', [])}
    route_map_in_id = None 

    if name in existing_peers:
        print(f"    [*] Updating BGP Peer '{name}'...")
        peer_obj = existing_peers[name]
        peer_obj.update({
            "description": peer_data.get('description', ''),
            "peer_ip": peer_data['peer_ip'],
            "remote_as_num": str(peer_data['peer-asn']),
            "peer_type": "classic",
            "route_map_in_id": route_map_in_id,
            "route_map_out_id": rm_out_id,
            "vrf_context_id": vrf_id,
            "shutdown": False,
            "allow_v4_prefixes": True,
            "advertise_default_route": False
        })
        resp = sdk.put.bgppeers(site_id=site_id, element_id=element_id, bgppeer_id=peer_obj['id'], data=peer_obj)
    else:
        print(f"    [+] Creating BGP Peer '{name}'...")
        payload = {
            "name": name,
            "description": peer_data.get('description', ''),
            "peer_ip": peer_data['peer_ip'],
            "remote_as_num": str(peer_data['peer-asn']),
            "peer_type": "classic",
            "route_map_in_id": route_map_in_id,
            "route_map_out_id": rm_out_id,
            "vrf_context_id": vrf_id,
            "shutdown": False,
            "allow_v4_prefixes": True,
            "allow_v6_prefixes": False,
            "advertise_default_route": False,
            "scope": "local"
        }
        resp = sdk.post.bgppeers(site_id=site_id, element_id=element_id, data=payload)
    
    if resp.cgx_status:
        print(f"    [OK] BGP Peer '{name}' configured successfully.")
        return True
    else:
        print(f"    [!] Error configuring BGP peer: {resp.cgx_content}")
        return False

# ----------------------------------------------------------------------------
# Static Route Logic
# ----------------------------------------------------------------------------
def ensure_static_route(sdk, site_id, element_id, route_data, vrf_id):
    name = route_data['static-route-name']
    dest_pfx = route_data['static-route-dest-pfx']
    next_hop = route_data['static-route-next-hop']
    description = route_data.get('static-route-desc', '')

    # 1. Get existing static routes (API Endpoint: staticroutes)
    resp = sdk.get.staticroutes(site_id=site_id, element_id=element_id)
    if not resp.cgx_status:
        print(f"    [!] Error getting static routes: {resp.cgx_content}")
        return False
    
    existing_routes = {item['name']: item for item in resp.cgx_content.get('items', [])}
    
    # 2. Build Payload
    payload = {
        "name": name,
        "description": description,
        "destination_prefix": dest_pfx,
        "nexthops": [{
            "nexthop_ip": next_hop,
            "admin_distance": 1,
            "self": False,
            "nexthop_interface_id": None
        }],
        "scope": "local",
        "address_family": "ipv4",
        "vrf_context_id": vrf_id,
        "nexthop_reachability_probe": False,
        "network_context_id": None
    }

    # 3. Create or Update
    if name in existing_routes:
        print(f"    [*] Updating Static Route '{name}' ({dest_pfx} -> {next_hop})...")
        route_id = existing_routes[name]['id']
        resp = sdk.put.staticroutes(site_id=site_id, element_id=element_id, staticroute_id=route_id, data=payload)
    else:
        print(f"    [+] Creating Static Route '{name}' ({dest_pfx} -> {next_hop})...")
        resp = sdk.post.staticroutes(site_id=site_id, element_id=element_id, data=payload)
        
    if resp.cgx_status:
        print(f"    [OK] Static Route '{name}' configured successfully.")
        return True
    else:
        print(f"    [!] Error configuring static route: {resp.cgx_content}")
        return False

# ----------------------------------------------------------------------------
# Main Execution
# ----------------------------------------------------------------------------
def main():
    if not prismasase_settings:
        print("Error: prismasase_settings.py not found or invalid.")
        sys.exit(1)

    print("--- Logging in to Prisma SASE ---")
    sdk = prisma_sase.API(ssl_verify=False)
    sdk.interactive.login_secret(client_id=prismasase_settings.client_id,
                                 client_secret=prismasase_settings.client_secret,
                                 tsg_id=prismasase_settings.scope)

    print("\n--- Building ID Lookup Maps ---")
    site_name_to_id = {item['name']: item['id'] for item in sdk.get.sites().cgx_content.get('items', [])}
    print(f"  > Loaded {len(site_name_to_id)} sites.")

    element_lookup = {}
    for item in sdk.get.elements().cgx_content.get('items', []):
        if item.get('site_id') and item.get('name'):
            element_lookup[(item['site_id'], item['name'])] = item['id']
    print(f"  > Loaded {len(element_lookup)} elements.")

    vrf_name_to_id = {item['name']: item['id'] for item in sdk.get.vrfcontexts().cgx_content.get('items', [])}
    print(f"  > Loaded {len(vrf_name_to_id)} VRFs.")

    # --- Read CSV ---
    print(f"\n--- Reading {CSV_FILE} ---")
    try:
        with open(CSV_FILE, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        print(f"File {CSV_FILE} not found.")
        return

    success_count = 0
    fail_count = 0

    print(f"\n--- Processing {len(rows)} Rows ---")
    for idx, row in enumerate(rows, 1):
        # Strip whitespace from keys and values if CSV errors only!
        row = {k.strip(): v.strip() for k, v in row.items() if k and v}

        site_name = row.get('site-name')
        ion_name = row.get('ion-name')
        
        # BGP Fields
        peer_name = row.get('peer_name')
        bgp_vrf_name = row.get('vrf-name')

        # Static Route Fields
        sr_name = row.get('static-route-name')
        sr_dest = row.get('static-route-dest-pfx')
        sr_nh = row.get('static-route-next-hop')
        sr_vrf_name = row.get('static-route-vrf-name')
        sr_desc = row.get('static-route-desc')

        print(f"\nRow {idx}: Site='{site_name}', Element='{ion_name}'")

        if not site_name or not ion_name:
            print("    [!] Missing Site or Element Name. Skipping.")
            fail_count += 1
            continue

        site_id = site_name_to_id.get(site_name)
        element_id = element_lookup.get((site_id, ion_name)) if site_id else None
        
        if not site_id or not element_id:
            print(f"    [!] Error: Site or Element not found.")
            fail_count += 1
            continue

        row_activity = False

        # --- PROCESS BGP PEER ---
        if peer_name and bgp_vrf_name:
            vrf_id = vrf_name_to_id.get(bgp_vrf_name)
            if vrf_id:
                # Ensure Prereqs (Prefix List / Route Map)
                pl_name = row.get('preflix-list-name') or row.get('prefix-list-name')
                pl_id = ensure_prefix_list(sdk, site_id, element_id, pl_name) if pl_name else None
                rm_id = ensure_route_map(sdk, site_id, element_id, row.get('route-map-out-name'), pl_id) if pl_id else None
                
                if rm_id:
                    if create_bgp_peer(sdk, site_id, element_id, row, rm_id, vrf_id):
                        success_count += 1
                        row_activity = True
            else:
                 print(f"    [!] BGP VRF '{bgp_vrf_name}' not found.")
        
        # --- PROCESS STATIC ROUTE ---
        if sr_name and sr_dest and sr_nh:
            target_vrf_name = sr_vrf_name if sr_vrf_name else bgp_vrf_name
            target_vrf_id = vrf_name_to_id.get(target_vrf_name)

            if target_vrf_id:
                if ensure_static_route(sdk, site_id, element_id, row, target_vrf_id):
                    success_count += 1
                    row_activity = True
                else:
                    fail_count += 1
            else:
                print(f"    [!] Static Route VRF '{target_vrf_name}' not found.")
                fail_count += 1
        
        if not row_activity:
            print("    [i] No actionable BGP or Static Route configuration found (check CSV columns).")

    print("\n------------------------------------------------")
    print(f"Job Complete.")
    print("------------------------------------------------")

if __name__ == "__main__":
    main()
