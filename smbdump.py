#!/us/bin/python
import os
import sys
from pathlib import Path
import subprocess
try:    import argparse
except: print('argparse required, run: pip install argparse');    sys.exit(1)

version    =    "0.1"


#---------------------------------------------------------------------------    
def main():
    
    argument_parser =   argparse.ArgumentParser(usage=None,add_help=False)
    argument_parser.add_argument('-h','--help'                ,action='store_true',default=False                 ,dest='help'      ,required=False  )
    argument_parser.add_argument('-v','--version'             ,action='store_true',default=False                 ,dest='version'   ,required=False  )
    argument_parser.add_argument('-t','--target'              ,action='store'     ,default=None                  ,dest='target'    ,required=True   )
    argument_parser.add_argument('-U','--user'                ,action='store'     ,default=None                  ,dest='user'      ,required=False  )
    argument_parser.add_argument('-f','--destination-folder'  ,action='store'     ,default=None                  ,dest='folder'    ,required=False  )
    
    argument_parser_result      =   argument_parser.parse_args()
    option_help                 =   argument_parser_result.help
    option_version              =   argument_parser_result.version
    target                      =   argument_parser_result.target
    user                        =   argument_parser_result.user
    destination_folder          =   argument_parser_result.folder

    if(option_version):
        print(version)
        sys.exit(0)
    elif(option_help):
        print_usage()
        sys.exit(0)
    else:
        #create destination folder if it does not exist
        create_folder_if_not_exists(destination_folder)
        
        smb_root_tree       =   target
        local_root_tree     =   destination_folder
        pending_to_visit    =   [smb_root_tree]
        already_visited     =   []
        while(pending_to_visit != []):
            current_visit   =   pending_to_visit.pop(0)
            #print('Exploring '+current_visit)
            results         =   smbclient_ls(current_visit,user)
            #print(str(results))
            for current_object_found in results:
                current_object_found_type   =   current_object_found[0]
                current_object_name         =   current_object_found[1]
                whole_smb_path              =   current_visit+'/'+current_object_name
                whole_local_path            =   None
                aux_tokens                  =   whole_smb_path.strip('/').split('/')
                whole_local_path            =   local_root_tree+'/'+'/'.join(aux_tokens[1:])
                already_visited.append((current_object_found_type,whole_smb_path))
                if(current_object_found_type=='D'):
                    pending_to_visit.append(whole_smb_path)
                    create_folder_if_not_exists(whole_local_path)
                else:
                    aux_tokens                  =   whole_local_path.split('/')
                    whole_local_path_directory  =   '/'.join(aux_tokens[0:-1])
                    smbclient_get(whole_smb_path, whole_local_path_directory,user)
        already_visited.sort(key=lambda x:x[1])
        for i in already_visited:
            already_visited_type    =   i[0]
            already_visited_path    =   i[1]
            if(already_visited_type=='D'):  print('D '+already_visited_path)
            else:                           print('  '+already_visited_path)
        print('DONE')
#---------------------------------------------------------------------------    
def print_usage():
    result    =    "smbdump.py -t|--target <ip_or_hostname> -f|--destination-folder <folder> [-U|--user 'user%passowrd'] [-h|--help] [-v|--version]"
    result    +=    "-t|--target             :  specify target (//hostname or //ip)"
    result    +=    "-f|--destination-folder :  Specify absolute folder path to be dumped in"
    result    +=    "-U|--user               :  Optional. Specify user%password"
    result    +=    "-h|--help               :  Prints this help"
    result    +=    "-v|--version            :  Prints version"
    print(result)
#---------------------------------------------------------------------------    
def smbclient_ls(smb_target,user=None):
    result      =   []
    #1st call       : smbclient -L //target
    #2nd call       : smbclient //target/directory
    #remainder calls: smbclient //target
    #                 >cd a/b/c
    #                 >dir
    aux         =   smb_target.strip('/')
    aux_tokens  =   aux.split('/')
    is_first_call   =   len(aux_tokens)==1
    is_second_call  =   len(aux_tokens)==2
    arguments       =   ['smbclient']
    stdin_input     =   '\n'
    if(is_first_call):
        arguments.append("-L")
        arguments.append(smb_target)
    elif(is_second_call):
        stdin_input     =   '\ndir\n'
        arguments.append(smb_target)
    else:
        arguments.append('//'+aux_tokens[0]+'/'+aux_tokens[1])
        cd_directory    =   '/'.join(aux_tokens[2:])
        stdin_input     =   '\n'+'cd "'+cd_directory+'"\ndir\n'
        
    if(user!=None):
        arguments.append("-U")
        arguments.append(user)
    pipe                        =   subprocess.Popen(arguments,stdout=subprocess.PIPE,stdin=subprocess.PIPE)
    pipe.stdin.write(stdin_input.encode())
    cmd_output                  =   pipe.communicate()[0]
    pipe.stdin.close()
    cmd_output                  =   cmd_output.decode('utf-8')
    line_of_header              =   None
    type_column_begin_position  =   None
    lines                       =   cmd_output.split('\n')
    if(is_first_call):
        line_of_header              =   [x for x in lines if x.startswith('\tSharename')][0]
        type_column_begin_position  =   line_of_header.find('Type')
    for current_line in lines:
        if(is_first_call and current_line.startswith("\t") and not current_line.strip()=='Sharename       Type      Comment' and not current_line.strip()=='---------       ----      -------'):
            entry_name      =   current_line[0:type_column_begin_position].strip()   
            type_of_entry   =   'D' #TODO! if there were any files, how would they be marked? Need to find a smb server with at least one file at the root folder!
            if(entry_name not in ('.','..')):
                result.append((type_of_entry,entry_name))
        elif(not is_first_call and current_line.startswith("  ") and not current_line.startswith("   ")):
            tokens          =   current_line.strip().split(" ")
            tokens          =   [x for x in tokens if x!='']
            type_of_entry   =   tokens[-7]
            entry_name      =   ' '.join(tokens[0:-7])   
            if(entry_name not in ('.','..')):
                result.append((type_of_entry,entry_name))
            
    return result
#---------------------------------------------------------------------------    
def smbclient_get(smb_target,local_absolute_containing_folder,user=None):
    #if the local file exists, it overwrites it.
    aux                 =   smb_target.strip('/')
    aux_tokens          =   aux.split('/')
    smb_to_connect_to   =   '//'+aux_tokens[0]+'/'+aux_tokens[1]     #TODO! file in the root folder?
    smb_to_cd_to        =   '/'.join(aux_tokens[2:-1])
    arguments           =   ['smbclient',smb_to_connect_to]
    if(user!=None):
        arguments.append("-U")
        arguments.append(user)
    stdin_input         =   '\n'+'cd '+smb_to_cd_to+'\n'+'get "'+aux_tokens[-1]+'"'
    os.chdir(local_absolute_containing_folder)
    pipe                        =   subprocess.Popen(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.PIPE)
    pipe.stdin.write(stdin_input.encode())
    cmd_output                  =   pipe.communicate()[0]
    pipe.stdin.close()
    cmd_output                  =   cmd_output.decode('utf-8')
#---------------------------------------------------------------------------    
def create_folder_if_not_exists(absolute_path):
    fd = Path(absolute_path)
    if(not fd.is_dir()):
        os.mkdir(absolute_path)
        
#---------------------------------------------------------------------------    
if(__name__ == '__main__'):
    main()
