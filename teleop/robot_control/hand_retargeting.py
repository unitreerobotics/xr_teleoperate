from dex_retargeting import RetargetingConfig
from pathlib import Path
import numpy as np
import yaml
from enum import Enum
import logging_mp
logger_mp = logging_mp.getLogger(__name__)

# Dex5-1 fingers extend along +Y of the hand base frame (base_link00L/R). 
# tv_wrapper delivers landmarks fingers-along--Y (Inspire/Dex3), so
# without this rotation the retargeter reaches behind the palm and saturates every
# proximal joint at pi/2 (a permanent fist). The sides need different matrices: the
# URDFs mirror in z, the landmarks in x, so one shared rotation would flip the
# spread axis on one hand.
DEX5_LANDMARK_ROTATION_LEFT = np.array([[0,  0, 1],
                                        [0, -1, 0],
                                        [1,  0, 0]], dtype=float)
DEX5_LANDMARK_ROTATION_RIGHT = np.array([[ 0,  0, -1],
                                         [ 0, -1,  0],
                                         [-1,  0,  0]], dtype=float)

class HandType(Enum):
    INSPIRE_HAND = "../assets/inspire_hand/inspire_hand.yml"
    INSPIRE_HAND_Unit_Test = "../../assets/inspire_hand/inspire_hand.yml"
    UNITREE_DEX5 = "../assets/unitree_hand_Dex5/unitree_dex5.yml"
    UNITREE_DEX5_Unit_Test = "../../assets/unitree_hand_Dex5/unitree_dex5.yml"
    UNITREE_DEX3 = "../assets/unitree_hand/unitree_dex3.yml"
    UNITREE_DEX3_Unit_Test = "../../assets/unitree_hand/unitree_dex3.yml"
    BRAINCO_HAND = "../assets/brainco_hand/brainco.yml"
    BRAINCO_HAND_Unit_Test = "../../assets/brainco_hand/brainco.yml"

class HandRetargeting:
    def __init__(self, hand_type: HandType):
        if hand_type == HandType.UNITREE_DEX5:
            RetargetingConfig.set_default_urdf_dir('../assets')
        elif hand_type == HandType.UNITREE_DEX5_Unit_Test:
            RetargetingConfig.set_default_urdf_dir('../../assets')
        elif hand_type == HandType.UNITREE_DEX3:
            RetargetingConfig.set_default_urdf_dir('../assets')
        elif hand_type == HandType.UNITREE_DEX3_Unit_Test:
            RetargetingConfig.set_default_urdf_dir('../../assets')
        elif hand_type == HandType.INSPIRE_HAND:
            RetargetingConfig.set_default_urdf_dir('../assets')
        elif hand_type == HandType.INSPIRE_HAND_Unit_Test:
            RetargetingConfig.set_default_urdf_dir('../../assets')
        elif hand_type == HandType.BRAINCO_HAND:
            RetargetingConfig.set_default_urdf_dir('../assets')
        elif hand_type == HandType.BRAINCO_HAND_Unit_Test:
            RetargetingConfig.set_default_urdf_dir('../../assets')

        config_file_path = Path(hand_type.value)

        # Applied to the (25,3) landmarks before retargeting; only Dex5 needs a correction.
        self.left_landmark_rotation = np.eye(3)
        self.right_landmark_rotation = np.eye(3)
        if hand_type in (HandType.UNITREE_DEX5, HandType.UNITREE_DEX5_Unit_Test):
            self.left_landmark_rotation = DEX5_LANDMARK_ROTATION_LEFT
            self.right_landmark_rotation = DEX5_LANDMARK_ROTATION_RIGHT

        try:
            with config_file_path.open('r') as f:
                self.cfg = yaml.safe_load(f)
                
            if 'left' not in self.cfg or 'right' not in self.cfg:
                raise ValueError("Configuration file must contain 'left' and 'right' keys.")

            left_retargeting_config = RetargetingConfig.from_dict(self.cfg['left'])
            right_retargeting_config = RetargetingConfig.from_dict(self.cfg['right'])
            self.left_retargeting = left_retargeting_config.build()
            self.right_retargeting = right_retargeting_config.build()

            self.left_retargeting_joint_names = self.left_retargeting.joint_names
            self.right_retargeting_joint_names = self.right_retargeting.joint_names
            self.left_indices = self.left_retargeting.optimizer.target_link_human_indices
            self.right_indices = self.right_retargeting.optimizer.target_link_human_indices

            if hand_type == HandType.UNITREE_DEX3 or hand_type == HandType.UNITREE_DEX3_Unit_Test:
                # In section "Sort by message structure" of https://support.unitree.com/home/en/G1_developer/dexterous_hand
                self.left_dex3_api_joint_names  = [ 'left_hand_thumb_0_joint', 'left_hand_thumb_1_joint', 'left_hand_thumb_2_joint',
                                                    'left_hand_middle_0_joint', 'left_hand_middle_1_joint', 
                                                    'left_hand_index_0_joint', 'left_hand_index_1_joint' ]
                self.right_dex3_api_joint_names = [ 'right_hand_thumb_0_joint', 'right_hand_thumb_1_joint', 'right_hand_thumb_2_joint',
                                                    'right_hand_middle_0_joint', 'right_hand_middle_1_joint',
                                                    'right_hand_index_0_joint', 'right_hand_index_1_joint' ]
                self.left_dex_retargeting_to_hardware = [ self.left_retargeting_joint_names.index(name) for name in self.left_dex3_api_joint_names]
                self.right_dex_retargeting_to_hardware = [ self.right_retargeting_joint_names.index(name) for name in self.right_dex3_api_joint_names]

            elif hand_type == HandType.UNITREE_DEX5 or hand_type == HandType.UNITREE_DEX5_Unit_Test:
                self.left_dex5_api_joint_names  = ["Roll_21L", "Pitch_22L", "Pitch_23L", "Pitch_24L", "Roll_31L", "Pitch_32L", "Pitch_33L",
                                                   "Pitch_34L", "Roll_41L", "Pitch_42L", "Pitch_43L", "Pitch_44L", "Roll_51L", "Pitch_52L",
                                                   "Pitch_53L", "Pitch_54L", "Yaw_11L", "Roll_12L", "Pitch_13L", "Pitch_14L"]
                self.right_dex5_api_joint_names = ["Roll_21R", "Pitch_22R", "Pitch_23R", "Pitch_24R", "Roll_31R", "Pitch_32R", "Pitch_33R",
                                                   "Pitch_34R", "Roll_41R", "Pitch_42R", "Pitch_43R", "Pitch_44R", "Roll_51R", "Pitch_52R",
                                                   "Pitch_53R", "Pitch_54R", "Yaw_11R", "Roll_12R", "Pitch_13R", "Pitch_14R"]
                self.left_dex_retargeting_to_hardware = [ self.left_retargeting_joint_names.index(name) for name in self.left_dex5_api_joint_names]
                self.right_dex_retargeting_to_hardware = [ self.right_retargeting_joint_names.index(name) for name in self.right_dex5_api_joint_names]

            elif hand_type == HandType.INSPIRE_HAND or hand_type == HandType.INSPIRE_HAND_Unit_Test:
                # "Joint Motor Sequence" of https://support.unitree.com/home/en/G1_developer/inspire_dfx_dexterous_hand
                self.left_inspire_api_joint_names  = [ 'L_pinky_proximal_joint', 'L_ring_proximal_joint', 'L_middle_proximal_joint',
                                                       'L_index_proximal_joint', 'L_thumb_proximal_pitch_joint', 'L_thumb_proximal_yaw_joint' ]
                self.right_inspire_api_joint_names = [ 'R_pinky_proximal_joint', 'R_ring_proximal_joint', 'R_middle_proximal_joint',
                                                       'R_index_proximal_joint', 'R_thumb_proximal_pitch_joint', 'R_thumb_proximal_yaw_joint' ]
                self.left_dex_retargeting_to_hardware = [ self.left_retargeting_joint_names.index(name) for name in self.left_inspire_api_joint_names]
                self.right_dex_retargeting_to_hardware = [ self.right_retargeting_joint_names.index(name) for name in self.right_inspire_api_joint_names]
            
            elif hand_type == HandType.BRAINCO_HAND or hand_type == HandType.BRAINCO_HAND_Unit_Test:
                # "Driver Motor ID" of https://www.brainco-hz.com/docs/revolimb-hand/product/parameters.html
                self.left_brainco_api_joint_names  = [ 'left_thumb_metacarpal_joint', 'left_thumb_proximal_joint', 'left_index_proximal_joint',
                                                       'left_middle_proximal_joint', 'left_ring_proximal_joint', 'left_pinky_proximal_joint' ]
                self.right_brainco_api_joint_names = [ 'right_thumb_metacarpal_joint', 'right_thumb_proximal_joint', 'right_index_proximal_joint',
                                                       'right_middle_proximal_joint', 'right_ring_proximal_joint', 'right_pinky_proximal_joint' ]
                self.left_dex_retargeting_to_hardware = [ self.left_retargeting_joint_names.index(name) for name in self.left_brainco_api_joint_names]
                self.right_dex_retargeting_to_hardware = [ self.right_retargeting_joint_names.index(name) for name in self.right_brainco_api_joint_names]
        
        except FileNotFoundError:
            logger_mp.warning(f"Configuration file not found: {config_file_path}")
            raise
        except yaml.YAMLError as e:
            logger_mp.warning(f"YAML error while reading {config_file_path}: {e}")
            raise
        except Exception as e:
            logger_mp.error(f"An error occurred: {e}")
            raise