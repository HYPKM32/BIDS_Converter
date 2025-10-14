"""
Reorienter Module
Handles NIfTI image reorientation using Nipype
"""

import os
import shutil
from pathlib import Path
from nipype.interfaces.image import Reorient


class Reorienter:
    """
    Reorients NIfTI images to specified orientation.
    
    Attributes:
        orientation (str): Target orientation (e.g., 'RAS', 'LPS', 'LPI')
    """
    
    def __init__(self, orientation='RAS'):
        """
        Initialize Reorienter with target orientation.
        
        Args:
            orientation (str): Target orientation code (default: 'RAS')
        """
        self.orientation = orientation.upper()
        
    def reorient(self, input_path, output_path):
        """
        Reorient NIfTI image to target orientation.
        
        Args:
            input_path (str): Path to input NIfTI file
            output_path (str): Path to save reoriented file
            
        Returns:
            str: Path to the reoriented output file
            
        Raises:
            RuntimeError: If reorientation fails
            FileNotFoundError: If input file not found
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Create output directory if needed
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Create working directory for temporary files
        working_dir = os.path.join(output_dir, '.reorient_temp')
        os.makedirs(working_dir, exist_ok=True)
        
        try:
            print(f"  Reorienting to {self.orientation}...")
            
            # Initialize Nipype Reorient interface
            reorient = Reorient(orientation=self.orientation)
            
            # Set input file
            reorient.inputs.in_file = input_path
            
            # Change to working directory for Nipype execution
            original_cwd = os.getcwd()
            os.chdir(working_dir)
            
            # Run reorientation
            result = reorient.run()
            
            # Return to original directory
            os.chdir(original_cwd)
            
            # Get output file from result
            temp_output = result.outputs.out_file
            
            # Nipype generates filename with suffix based on orientation
            # Example: input_ras.nii.gz for RAS orientation
            expected_suffix = f"_{self.orientation.lower()}.nii.gz"
            
            # Check if output file was created
            if not os.path.exists(temp_output):
                # Sometimes Nipype doesn't change the file if already in correct orientation
                # In this case, just copy the input
                print(f"  Image already in {self.orientation} orientation, copying...")
                shutil.copy2(input_path, output_path)
            else:
                # Move the reoriented file to final destination
                shutil.copy2(temp_output, output_path)
            
            print(f"  Reorientation complete!")
            
            return output_path
            
        except Exception as e:
            raise RuntimeError(f"Reorientation failed: {str(e)}")
            
        finally:
            # Clean up working directory
            if os.path.exists(working_dir):
                try:
                    shutil.rmtree(working_dir)
                except:
                    pass  # Ignore cleanup errors
    
    def get_current_orientation(self, input_path):
        """
        Get current orientation of NIfTI image.
        
        Args:
            input_path (str): Path to NIfTI file
            
        Returns:
            str: Current orientation code (e.g., 'RAS', 'LPS')
            
        Note:
            This requires nibabel to read the header information.
        """
        try:
            import nibabel as nib
            img = nib.load(input_path)
            return nib.aff2axcodes(img.affine)
        except ImportError:
            return "Unknown (nibabel not installed)"
        except Exception as e:
            return f"Unknown (error: {str(e)})"