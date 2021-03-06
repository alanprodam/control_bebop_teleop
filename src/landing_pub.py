#!/usr/bin/env python
from __future__ import print_function
 
import roslib
roslib.load_manifest('control_bebop_teleop')

import time, math
import sys, select, termios, tty
import rospy
import tf
import cv2

# numpy and scipy
import numpy as np
import cv2.aruco as aruco
from std_msgs.msg import Empty
from std_msgs.msg import String
from nav_msgs.msg import Odometry, Path
from geometry_msgs.msg import PoseWithCovarianceStamped, PoseStamped
from geometry_msgs.msg import Point, Pose, Quaternion, Twist, Vector3

drone_pose = Odometry()

path_drone = Path()

msg_aruco = "Empty"

landing = True

msg = """
Keyboard commands for Autonomous Landing of the Quadcopter
----------------------------------------------------------
TakeOff      - Press 1
Landing      - Press 2
MoveCamera   - Press 3
MoveUp       - Press 4
MoveDown     - Press 5
Auto-Landing - Press 6
----------------------------------------------------------
Ctrl + C to quit
"""

###############################################################################

def getKey():
  tty.setraw(sys.stdin.fileno())
  select.select([sys.stdin], [], [], 0)
  key = sys.stdin.read(1)
  termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
  return key

###############################################################################

def callbackPoseAruco(posedata):
  global path_drone, drone_pose

  # recive date of odometry aruco
  drone_pose = posedata

  poseStamped = PoseStamped()
  poseStamped.header.seq = posedata.header.seq
  poseStamped.header.frame_id = "path_drone"
  poseStamped.header.stamp = rospy.Time.now()
  poseStamped.pose = posedata.pose.pose
  
  path_drone.header = poseStamped.header
  path_drone.poses.append(poseStamped)

  path_pub.publish(path_drone)


###############################################################################

def moveCamera():

  cam_twist = Twist()

  #-- set camera, look to dwn
  cam_twist.angular.x = 0
  cam_twist.angular.y = -84
  cam_twist.angular.z = 0
  cam_pub.publish(cam_twist)
  print('angle_camera: ',cam_twist.angular.y)

  return cam_twist.angular.y

###############################################################################

def moveUp():
  global drone_pose

  velocity = Twist()

  cont = 0

  while not rospy.is_shutdown() and cont < 500:

    #print('init cont: ', cont)
    velocity.linear.x = 0
    velocity.linear.y = 0
    velocity.linear.z = 1 # velocity.linear.z = 1 para subir


    velocity.angular.x = 0
    velocity.angular.y = 0
    velocity.angular.z = 0
    vel_drone_pub.publish(velocity)

    cont += 1
    print('Z with Aruco:',drone_pose.pose.pose.position.z)

    # print('velocity-linear-X: {} - velocity-linear-Y: {} - velocity-linear-Z: {}'.format(velocity.linear.x, velocity.linear.y, velocity.linear.z))
    rate.sleep()

 ###############################################################################

def moveDown():
  global drone_pose
  
  velocity = Twist()

  cont = 0

  while not rospy.is_shutdown() and cont < 500:

    #print('init cont: ', cont)
    velocity.linear.x = 0
    velocity.linear.y = 0
    velocity.linear.z = -1

    velocity.angular.x = 0
    velocity.angular.y = 0
    velocity.angular.z = 0
    vel_drone_pub.publish(velocity)

    cont += 1
    print('Z with Aruco:',drone_pose.pose.pose.position.z)

    # print('velocity-linear-X: {} - velocity-linear-Y: {} - velocity-linear-Z: {}'.format(velocity.linear.x, velocity.linear.y, velocity.linear.z))
    rate.sleep()

  ###############################################################################

def autoLanding():
  global landing, drone_pose

  # z data orientation -- 20m
  k = 2e-3
  ki = 6e-4
  eyawp = 0
  uyaw = 0

  # x data translation -- 20m

  k_x = 6e-2
  k_i_x = 4e-2
  exp = 0

  # k_x = 3e-2
  # k_i_x = 5e-3
  # exp = 0

  # y data translation -- 20m

  k_y = 6e-2
  k_i_y = 4e-2
  eyp = 0

  # k_y = 3e-2
  # k_i_y = 5e-3
  # eyp = 0

  tolerance_Yaw = 3
  tolerance_X = 0.05
  tolerance_Y = 0.05

  empty_msg = Empty()
  
  velocity_drone = Twist()

  angle_camera = moveCamera()

  while not rospy.is_shutdown() and landing:

    current_time = rospy.Time.now()
    dt = (current_time - drone_pose.header.stamp).to_sec()
    #print('********tempo dt: {} current_time {} pose.header.stamp {}'.format(dt,current_time.to_sec(),drone_pose.header.stamp.to_sec()))

    if(dt > 1):
      #rospy.loginfo('**id_aruco = False')
      id_aruco = False
      velocity_drone.linear.y = 0
      velocity_drone.linear.x = 0
      velocity_drone.linear.z = 0

      velocity_drone.angular.x = 0
      velocity_drone.angular.y = 0
      velocity_drone.angular.z = 0
      vel_drone_pub.publish(velocity_drone)
    else:
      #rospy.loginfo('**id_aruco = True')
      id_aruco = True

    if angle_camera == -84 and id_aruco == True:

      # recive the position
      linearx = drone_pose.pose.pose.position.x
      lineary = drone_pose.pose.pose.position.y
      linearz = drone_pose.pose.pose.position.z

      # recive the orientation
      euler = tf.transformations.euler_from_quaternion([drone_pose.pose.pose.orientation.x, 
                                                      drone_pose.pose.pose.orientation.y, 
                                                      drone_pose.pose.pose.orientation.z, 
                                                      drone_pose.pose.pose.orientation.w]) #roll, pitch, yaw
      angularz = math.degrees(euler[2])
      modulo_distancia = math.sqrt(linearx*linearx + lineary*lineary)

      # Condition for translation in Yaw
      if abs(angularz) > (tolerance_Yaw+linearz*0.1) and abs(modulo_distancia) <= 2.0:
        kp_Yaw = k*angularz
        ki_Yaw = (angularz+eyawp)*ki
        #ki_Yaw = 0
        uyaw = kp_Yaw + ki_Yaw
        eyawp = angularz
        print('correcting tolerance Yaw: {} - Uyaw: {} - kp_Yaw: {} - ki_Yaw: {}'.format((tolerance_Yaw+linearz*0.1), uyaw, kp_Yaw, ki_Yaw))
      else:
        uyaw = 0
        print('Yaw close to 0')

      #Condition for translation in X
      if abs(linearx) > (tolerance_X+linearz*0.06):
        kp_x = (k_x/(linearz+1))*linearx
        ki_x = (linearx+exp)*k_i_x
        #ki_x = 0
        u_x = (kp_x + ki_x)
        exp = linearx
        print('correcting tolerance X: {} *** u_x: {}'.format((tolerance_X+linearz*0.06), u_x))
      else:
        kp_x = (k_x/(linearz+1))*linearx
        ki_x = (linearx+exp)*k_i_x
        #ki_x = 0
        u_x = (kp_x + ki_x)
        exp = linearx
        print('X close to 0')
      
      # Condition for translation in y
      if abs(lineary) > (tolerance_Y+linearz*0.06):
        kp_y = (k_y/(linearz+1))*lineary
        ki_y = (lineary+eyp)*k_i_y
        #ki_y = 0
        u_y = (kp_y + ki_y)
        eyp = lineary
        print('correcting tolerance Y: {} *** u_y: {}'.format((tolerance_Y+linearz*0.06), u_y))
      else:
        kp_y = (k_y/(linearz+1))*lineary
        ki_y = (lineary+eyp)*k_i_y
        #ki_y = 0
        u_y = (kp_y + ki_y)
        eyp = lineary
        print('Y close to 0')

      # Condition for translation in z
      if abs(linearz) > 1.0 and abs(linearx) <= (tolerance_X+linearz*0.06) and abs(lineary) <= (tolerance_Y+linearz*0.06) and abs(angularz) <= (tolerance_Yaw+linearz*0.1):
        u_z = -1.0
        #print('correcting tolerance X: {} - Ux: {} - kp_x: {} - ki_x: {}'.format((tolerance_X+linearz*0.08), u_x, kp_x, ki_x))
        #print('correcting tolerance Y: {} - Uy: {} - kp_y: {} - ki_y: {}'.format((tolerance_Y+linearz*0.08), u_y, kp_y, ki_y))
        rospy.loginfo('Drone Landing!')
      else:
        u_z = 0
        rospy.loginfo('Drone is not Landing!')

      # Condition landing
      if abs(linearz) <= 1.2 and abs(linearx) <= (tolerance_X+linearz*0.06) and abs(lineary) <= (tolerance_Y+linearz*0.06) and abs(angularz) <= (tolerance_Yaw+linearz*0.1):
        velocity_drone.linear.y = 1.0
        rospy.sleep(5)
        rospy.loginfo('rospy.sleep(5)')
        vel_drone_pub.publish(velocity_drone)
        land_pub.publish(empty_msg)
        rospy.loginfo('Auto-Landing Performed!')
        landing = False
        break

      velocity_drone.linear.y = u_x
      velocity_drone.linear.x = -u_y
      velocity_drone.linear.z = u_z
      
      #print('correcting rotation Yaw - ', (tolerance_Yaw+linearz*0.1))

      velocity_drone.angular.x = 0
      velocity_drone.angular.y = 0
      velocity_drone.angular.z = uyaw
      vel_drone_pub.publish(velocity_drone)
      #print("modulo distancia: {} - uyaw: {}".format(modulo_distancia,uyaw))


    else:
      rospy.loginfo('Auto-Landing not Performed!')
      velocity_drone.linear.y = 0
      velocity_drone.linear.x = 0
      velocity_drone.linear.z = 0

      velocity_drone.angular.x = 0
      velocity_drone.angular.y = 0
      velocity_drone.angular.z = 0
      vel_drone_pub.publish(velocity_drone)


    rospy.loginfo('-----------------------------------------')
    rate.sleep()

###############################################################################
   
if __name__ == '__main__':
  settings = termios.tcgetattr(sys.stdin)
  rospy.init_node('landing_aruco')

  # create the important subscribers
  pose_sub = rospy.Subscriber("bebop/pose_aruco",Odometry, callbackPoseAruco)

  # create the important publishers
  cam_pub = rospy.Publisher("bebop/camera_control",Twist, queue_size = 100)
  vel_drone_pub = rospy.Publisher("bebop/cmd_vel",Twist, queue_size = 100)
  path_pub = rospy.Publisher("bebop/path_odom", Path, queue_size = 100)

  # create the publishers to take off and land
  takeoff_pub = rospy.Publisher('bebop/takeoff', Empty, queue_size = 100) # add a publisher for each new topic
  land_pub = rospy.Publisher('bebop/land', Empty, queue_size = 100)    # add a publisher for each new topic
  
  empty_msg = Empty() 

  rate = rospy.Rate(100.0) #-- 100Hz

  print('Program Started')
  print(msg)

  try:
    while(1):
      key = getKey()
      print('key')  # add a print for each key pressed
      print(key)

      if key == '1': # condition created in order to pressed key 1 and generates the take off of the bebop2
        print('key 1 pressed - Takeoff')
        takeoff_pub.publish(empty_msg) # action to publish it
        print(msg)

      elif key == '2': # condition created in order to pressed key 2 and generates the land of the bebop2
        print('key 2 pressed - Landing')
        land_pub.publish(empty_msg) # action to publish it
        print(msg)

      elif key == '3': # condition created in order to pressed key 3 and generates the moviment of camera
        print('key 3 pressed - MoveCamera')
        moveCamera()
        print(msg)

      elif key == '4': # condition created in order to pressed key 4 and generates upward movement of the drone
        print('key 4 pressed - MoveUp')
        moveUp()
        print(msg)

      elif key == '5': # condition created in order to pressed key 5 and generates drone descent movement
        print('key 5 pressed - MoveDown')
        moveDown()
        print(msg)

      elif key == '6': # condition created in order to pressed key 6 and generates Auto-Landing of drone
        print('key 6 pressed - Auto-Landing') 
        autoLanding()
        print(msg)

      elif key == '\x03': # condition created in order to pressed key Ctrl+c and generates output from the program
          print('Quit work')
          break
      else:
        print('Wrong key!')
        print(msg)

      landing = True
      
  except rospy.ROSInterruptException:
    print('Erro')