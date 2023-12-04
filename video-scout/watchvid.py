import cv2
import numpy as np
import pytesseract

mode_white_thresh = 230

# Constants.
INPUT_WIDTH = 640
INPUT_HEIGHT = 640
SCORE_THRESHOLD = 0.5
NMS_THRESHOLD = 0.45
CONFIDENCE_THRESHOLD = 0.2

# Text parameters.
FONT_FACE = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.7
THICKNESS = 1

# Colors.
BLACK  = (0,0,0)
BLUE   = (255,178,50)
YELLOW = (0,255,255)

# Constants for points on the screen -- will change between events, needs to
# be a bit more dynamic

field_pts = np.array([
    [200, 450],
    [1650, 480],
    [1920, 820],
    [2, 800]], np.int32)
field_pts = field_pts.reshape((-1, 1, 2))


timer_sw = 160
timer_sh = 80
timer_tl = (880, 80)
timer_br = (timer_tl[0]+timer_sw, timer_tl[1]+timer_sh)

# The area of the scoreboard where 'mode' is being signaled, Auton, or teleop
mode_tl = (910, 160)
mode_sw = 100
mode_sh = 50
mode_br = (mode_tl[0]+mode_sw, mode_tl[1]+mode_sh)


def draw_label(im, label, x, y):
    """Draw text onto image at location."""
    # Get text size.
    text_size = cv2.getTextSize(label, FONT_FACE, FONT_SCALE, THICKNESS)
    dim, baseline = text_size[0], text_size[1]
    # Use text size to create a BLACK rectangle.
    cv2.rectangle(im, (x,y), (x + dim[0], y + dim[1] + baseline), (0,0,0), cv2.FILLED);
    # Display text inside the rectangle.
    cv2.putText(im, label, (x, y + dim[1]), FONT_FACE, FONT_SCALE, YELLOW, THICKNESS, cv2.LINE_AA)


def pre_process(input_image, net):
    # Create a 4D blob from a frame.
    blob = cv2.dnn.blobFromImage(input_image, 1/255,  (INPUT_WIDTH, INPUT_HEIGHT), [0,0,0], 1, crop=False)

    # Sets the input to the network.
    net.setInput(blob)

    # Run the forward pass to get output of the output layers.
    outputs = net.forward(net.getUnconnectedOutLayersNames())
    return outputs


def post_process(input_image, outputs):
    # Lists to hold respective values while unwrapping.
    class_ids = []
    confidences = []
    boxes = []
    # Rows.
    rows = outputs[0].shape[1]
    image_height, image_width = input_image.shape[:2]
    # Resizing factor.
    x_factor = image_width / INPUT_WIDTH
    y_factor = image_height / INPUT_HEIGHT
    # Iterate through detections.
    for r in range(rows):
        row = outputs[0][0][r]
        confidence = row[4]
        # Discard bad detections and continue.
        if confidence >= CONFIDENCE_THRESHOLD:
            classes_scores = row[5:]
            # Get the index of max class score.
            class_id = np.argmax(classes_scores)
            print('class_id', class_id)
            #  Continue if the class score is above threshold.
            if (classes_scores[class_id] > SCORE_THRESHOLD):
                confidences.append(confidence)
                class_ids.append(class_id)
                cx, cy, w, h = row[0], row[1], row[2], row[3]
                left = int((cx - w/2) * x_factor)
                top = int((cy - h/2) * y_factor)
                width = int(w * x_factor)
                height = int(h * y_factor)
                box = np.array([left, top, width, height])
                boxes.append(box)
    # Perform non maximum suppression to eliminate redundant, overlapping boxes with lower confidences.
    indices = cv2.dnn.NMSBoxes(boxes, confidences, CONFIDENCE_THRESHOLD, NMS_THRESHOLD)
    for i in indices:
        box = boxes[i]
        left = box[0]
        top = box[1]
        width = box[2]
        height = box[3]
        # Draw bounding box.
        cv2.rectangle(input_image, (left, top), (left + width, top + height), BLUE, 3*THICKNESS)
        # Class label.
        # label = "{}:{:.2f}".format(classes[class_ids[i]], confidences[i])
        label = "{}:{:.2f}".format(i, confidences[i])
        # Draw label.
        draw_label(input_image, label, left, top)
    return input_image


def _get_mode_area(frame):
    mode_area = frame[mode_tl[1]:mode_tl[1] + mode_sh,
                      mode_tl[0]:mode_tl[0] + mode_sw]
    return mode_area


def _get_mode_area_mean(frame):
    mode_area = _get_mode_area(frame)
    mode_gray = cv2.cvtColor(mode_area, cv2.COLOR_BGR2GRAY)
    mode_avg = np.mean(mode_gray)
    return mode_avg


def _frame_mode_empty(frame):
    mode_avg = _get_mode_area_mean(frame)
    if mode_avg >= mode_white_thresh:
        return True
    return False


def forward_to_blank_mode(cap):
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if _frame_mode_empty(frame):
            mode_area = _get_mode_area(frame)
            # cv2.imshow('blank', mode_area)
            # We have a pure white spot in the 'mode' section of the scoreboard
            return True, frame
    return False, None


def forward_to_next_mode(cap):
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if not _frame_mode_empty(frame):
            mode_area = _get_mode_area(frame)
            # cv2.imshow('next', mode_area)
            # We have a pure white spot in the 'mode' section of the scoreboard
            return True, frame
    return False, None


"""
if False:  # Hot mess
    tracker.init(frame, bbox)
    frame_id = 0
    ret, frame = cap.read()
    success, bbox = tracker.update(frame)
    if success:
        x, y, w, h = [int(i) for i in bbox]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
    cv2.imshow("Tracking", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    # Cropping the text block for giving input to OCR
    timer_area = frame[tl[1]:tl[1] + sh, tl[0]:tl[0] + sw]
    cv2.rectangle(frame, tl, br, (255, 0, 0), 2)

    text = pytesseract.image_to_string(cropped, config='--psm 7')
    if len(text) > 0:
        print(text)

    ret, frame = cap.read()
"""


def main():
    net = cv2.dnn.readNet('best.onnx')
    rootfile = 'qm03'
    vidfile = f'videos/2023micmp4_{rootfile}.mkv'
    print(vidfile)
    # pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
    # tracker = cv2.TrackerCSRT_create()
    cap = cv2.VideoCapture(vidfile)
    _, frame = forward_to_blank_mode(cap)
    _, frame = forward_to_next_mode(cap)
    cv2.imwrite(f'training_images/{rootfile}_01.png', frame)
    mode = 'auto'
    # Start the tracker
    counter = 0
    ticker = 2
    _, frame = cap.read()
    while True:
        cv2.rectangle(frame, mode_tl, mode_br, (0, 255, 0), 2)
        cv2.polylines(frame, [field_pts], True, (0, 255, 255), 8)
        ftl_x = 2
        ftl_y = 450
        fbr_x = 1920
        fbr_y = 820
        field_area = frame[ftl_y:fbr_y, ftl_x:fbr_x]
        detections = pre_process(field_area, net)
        # print(detections)
        img = post_process(field_area.copy(), detections)
        scale = 2/3
        scaled = cv2.resize(img, (0, 0), fx=scale, fy=scale)
        cv2.imshow(mode, scaled)
        import time
        time.sleep(0.02)
        _, frame = cap.read()
        counter += 1
        if counter == 30:
            cv2.imwrite(f'training_images/{rootfile}_{ticker:02}.png', frame)
            ticker += 1
            counter = 0
        if _frame_mode_empty(frame):
            pass
            # break
            # _, frame = forward_to_next_mode(cap)
            # mode = 'tele'

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
