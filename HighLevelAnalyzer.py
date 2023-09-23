# High Level Analyzer
# For more information and documentation, please go to https://support.saleae.com/extensions/high-level-analyzer-extensions

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, NumberSetting, ChoicesSetting

def binstr2hexstr( s ):
    return "0" if s=="" else hex( int( s, 2 ) )   
        
# High level analyzers must subclass the HighLevelAnalyzer class.
class Hla(HighLevelAnalyzer):
    # List of settings that a user can set for this High Level Analyzer.
    my_string_setting = StringSetting()
    my_number_setting = NumberSetting(min_value=0, max_value=100)
    my_choices_setting = ChoicesSetting(choices=('A', 'B'))

    # An optional list of types this analyzer produces, providing a way to customize the way frames are displayed in Logic 2.
    result_types = {
        'intermediate': {
            'format': '{{data.instate}}->{{data.outstate}} TDI={{data.to_target}} TDO={{data.to_host}}'
        },

        'update-ir': {
            'format': 'UPDATE-IR TDI=x{{data.to_target}} TDO=x{{data.to_host}}'
        },

        'update-dr': {
            'format': 'UPDATE-DR TDI=x{{data.to_target}} TDO=x{{data.to_host}}'
        }


    }

    def bool2str(self, b):
        return "1" if b else "0"


    def __init__(self):
        '''
        Initialize HLA.

        Settings can be accessed using the same name used above.
        '''

        print("Settings:", self.my_string_setting,
              self.my_number_setting, self.my_choices_setting)
        

        self.state = 'RUN-TEST/IDLE'

        self.ir_bits_to_host = ""
        self.ir_bits_to_target = ""

        self.dr_bits_to_host = ""
        self.dr_bits_to_target = ""        

    def advance_state_machine(self, tms):
        print("tms=" + ("t" if tms else  " f" )+ " state="+self.state )
        # Intro "tree"
        if self.state == 'TEST-LOGIC-RESET':
            self.state = 'TEST-LOGIC-RESET' if (tms) else 'RUN-TEST/IDLE'
        elif self.state == 'RUN-TEST/IDLE':
            self.state = 'SELECT-DR-SCAN' if (tms) else 'RUN-TEST/IDLE'
        # DR "tree"
        elif self.state == 'SELECT-DR-SCAN':
            self.state = 'SELECT-IR-SCAN' if (tms) else 'CAPTURE-DR'
        elif self.state == 'CAPTURE-DR':
            self.state = 'EXIT1-DR' if (tms) else 'SHIFT-DR'
        elif self.state == 'SHIFT-DR':
            self.state = 'EXIT1-DR' if (tms) else 'SHIFT-DR'
        elif self.state == 'EXIT1-DR':
            self.state = 'UPDATE-DR' if (tms) else 'PAUSE-DR'
        elif self.state == 'PAUSE-DR':
            self.state = 'EXIT2-DR' if (tms) else 'PAUSE-DR'
        elif self.state == 'EXIT2-DR':
            self.state = 'UPDATE-DR' if (tms) else 'SHIFT-DR'
        elif self.state == 'UPDATE-DR':
            self.state = 'SELECT-DR-SCAN' if (tms) else 'RUN-TEST/IDLE'
        # IR "tree"
        elif self.state == 'SELECT-IR-SCAN':
            self.state = 'TEST-LOGIC-RESET' if (tms) else 'CAPTURE-IR'
        elif self.state == 'CAPTURE-IR':
            self.state = 'EXIT1-IR' if (tms) else 'SHIFT-IR'
        elif self.state == 'SHIFT-IR':
            self.state = 'EXIT1-IR' if (tms) else 'SHIFT-IR'
        elif self.state == 'EXIT1-IR':
            self.state = 'UPDATE-IR' if (tms) else 'PAUSE-IR'
        elif self.state == 'PAUSE-IR':
            self.state = 'EXIT2-IR' if (tms) else 'PAUSE-IR'
        elif self.state == 'EXIT2-IR':
            self.state = 'UPDATE-IR' if (tms) else 'SHIFT-IR'
        elif self.state == 'UPDATE-IR':
            self.state = 'SELECT-DR-SCAN' if (tms) else 'RUN-TEST/IDLE'
        else:
            raise Exception('Invalid state: %s' % self.state)

    
    def decode(self, frame: AnalyzerFrame):
        '''
        Process a frame from the input analyzer, and optionally return a single `AnalyzerFrame` or a list of `AnalyzerFrame`s.

        The type and data values in `frame` will depend on the input analyzer.
        '''

        print( frame.data )

        print( "frame tms=" + ("1" if frame.data['tms'] else "0" ))

        # We will process based on the previous frame's state
        # This is becuase the TDI and TDO signals lag by one frame
        prevState = self.state

        self.advance_state_machine(frame.data['tms'])    

        if prevState == "CAPTURE-DR":
            self.dr_bits_to_host = ""
            self.dr_bits_to_target = ""

        elif prevState == "SHIFT-DR":
            # This macro loads a 16-bit word into the JTAG data register (DR) (in the MSP430 devices, a data register is
            # 16 bits wide). The data word is shifted, most significant bit (MSB) first, into the TDI input of the target MSP430
            # device.
            self.dr_bits_to_target = self.dr_bits_to_target + self.bool2str( frame.data[ 'tdi' ] ) 
            # ...which means they are shifted to the host MSB first
            self.dr_bits_to_host =   self.bool2str( frame.data[ 'tdo' ]) +self.dr_bits_to_host 
            
        elif prevState== "UPDATE-DR":            
            # Return a decoded reg update
            to_target_hexstr  = binstr2hexstr( self.dr_bits_to_target )
            to_host_hexstr    = binstr2hexstr( self.dr_bits_to_host )

            return AnalyzerFrame('update-dr', frame.start_time, frame.end_time, {
                'reg': "dr",
                'to_target': to_target_hexstr,
                'to_host':  to_host_hexstr, 
            })        
        
        elif prevState == "CAPTURE-IR":
            self.ir_bits_to_host = ""
            self.ir_bits_to_target = ""

        elif prevState== "SHIFT-IR":
            # 8 bits are shiftd to the taget LSB first
            self.ir_bits_to_target = self.bool2str( frame.data[ 'tdi' ] ) +  self.ir_bits_to_target 
            # ...which means they are shifted to the host MSB first
            self.ir_bits_to_host =  self.ir_bits_to_host + self.bool2str( frame.data[ 'tdo' ])
            
        elif prevState == "UPDATE-IR":            
            # Return a decoded reg update

            to_target_hexstr  = binstr2hexstr( self.ir_bits_to_target )
            to_host_hexstr    = binstr2hexstr( self.ir_bits_to_host )

            if to_target_hexstr=="0x83":
                instruction = "IR_ADDR_16BIT"
            elif to_target_hexstr=="0x84":
                instruction = "IR_ADDR_CAPTURE"
            elif to_target_hexstr=="0x85":  
                instruction = "IR_DATA_TO_ADDR"
            elif to_target_hexstr=="0x41":
                instruction = "IR_DATA_16BIT"
            elif to_target_hexstr=="0x43":
                instruction = "IR_DATA_QUICK"
            elif to_target_hexstr=="0xFF":  
                instruction = "IR_BYPASS"
            elif to_target_hexstr=="0x13":  
                instruction = "IR_CNTRL_SIG_16BIT"
            elif to_target_hexstr == "0x14":
                instruction = "IR_CNTRL_SIG_CAPTURE"
            elif to_target_hexstr == "0x15":
                instruction = "IR_CNTRL_SIG_RELEASE"
            elif to_target_hexstr == "0x44": 
                instruction = "IR_DATA_PSA" 
            elif to_target_hexstr == "0x46":
                instruction = "IR_SHIFT_OUT_PSA"
            elif to_target_hexstr == "0x22":
                instruction = "IR_PREPARE_BLOW"
            elif to_target_hexstr == "0x24":
                instruction = "IR_EX_BLOW"
            elif to_target_hexstr == "0x61":
                instruction = "IR_JMB_EXCHANGE"
            else :
                instruction = "UNKNOWN"


            
            return AnalyzerFrame('update-ir', frame.start_time, frame.end_time, {
                'reg': "ir",
                'to_target':  to_target_hexstr,
                'to_host':  to_host_hexstr,
                'instruction': instruction,
            })
        
 
        """
        return AnalyzerFrame('intermediate', frame.start_time, frame.end_time, {
            'instate': prevState,
            'outstate': self.state,
            'to_target':  self.ir_bits_to_target,
            'to_host':  self.ir_bits_to_host,
        })
        """


        # Only return a frame if we were in an update state to make it easier to find these.
